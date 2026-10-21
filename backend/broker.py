"""Alpaca PAPER execution only. Real-money URLs and account resets are unsupported."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
import os
from pathlib import Path
import time
from uuid import UUID

import httpx
from .market import SYMBOLS
from .provider import credentials

PAPER_URL = 'https://paper-api.alpaca.markets'
TERMINAL = {'filled', 'canceled', 'expired', 'rejected', 'done_for_day'}


class BrokerError(RuntimeError):
    pass


class AlpacaPaper:
    def __init__(self, *, client=None, journal=None):
        key, secret = credentials()
        self.headers = {'APCA-API-KEY-ID':key, 'APCA-API-SECRET-KEY':secret}
        self.client = client or httpx.AsyncClient(timeout=10, follow_redirects=False)
        self.owned_client = client is None
        self.pending_id = None
        self.pending_client_id = None
        self.last_order = None
        self.snapshot = None
        self.journal = journal or Path(__file__).parent / 'data' / 'paper-orders.jsonl'

    async def request(self, method, path, *, allow_missing=False, **kwargs):
        # Fixed host, not an environment variable, user input, or SDK live/paper flag.
        url = PAPER_URL + '/v2/' + path
        response = await self.client.request(method, url, headers=self.headers, **kwargs)
        if allow_missing and response.status_code == 404:
            return None
        if response.status_code not in (200,201,204):
            raise BrokerError(f'Alpaca PAPER HTTP {response.status_code}; inspect the paper dashboard. No order is retried.')
        return response.json() if response.content else None

    def record(self, event, **fields):
        self.journal.parent.mkdir(exist_ok=True, parents=True)
        with self.journal.open('a', encoding='utf-8') as file:
            file.write(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(), 'event':event, **fields})+'\n')
            file.flush()
            os.fsync(file.fileno())

    async def account(self, symbol):
        if symbol not in SYMBOLS:
            raise BrokerError('Select AAPL, NVDA, or TSLA for Alpaca PAPER execution.')
        account = await self.request('GET','account')
        position = await self.request('GET',f'positions/{symbol}',allow_missing=True)
        qty = Decimal(str((position or {}).get('qty','0')))
        if account.get('status') != 'ACTIVE' or account.get('trading_blocked') or account.get('account_blocked'):
            raise BrokerError('Alpaca PAPER account is not active for trading.')
        if qty < 0 or qty > 100:
            raise BrokerError('Selected paper holding is short or exceeds 100 shares. Resolve it on Alpaca before running.')
        self.snapshot = {'environment':'alpaca_paper','cash':float(account['cash']),
                         'equity':float(account['equity']), 'buying_power':float(account['buying_power']),
                         'symbol':symbol,'position':float(qty),
                         'market_value':float((position or {}).get('market_value','0')),
                         'unrealized_pnl':float((position or {}).get('unrealized_pl','0')),
                         'timestamp':datetime.now(timezone.utc).isoformat(),'last_order':self.last_order}
        return self.snapshot

    async def preflight(self, symbol):
        await self.account(symbol)
        clock = await self.request('GET','clock')
        if not clock.get('is_open'):
            raise BrokerError('US regular market session is closed. Alpaca PAPER mode does not queue overnight orders; use local replay.')
        asset = await self.request('GET',f'assets/{symbol}')
        if not asset.get('tradable') or asset.get('status') != 'active':
            raise BrokerError('Selected stock is not tradable in the paper account.')
        await self.check_open_orders(symbol)

    async def check_open_orders(self, symbol):
        orders = await self.request('GET','orders',params={'status':'open','symbols':symbol,'limit':100})
        if orders:
            raise BrokerError('Selected stock already has open paper orders. Resolve them in Alpaca before continuing.')

    def order_view(self, order):
        return {key:order.get(key) for key in ('id','client_order_id','symbol','side','qty','filled_qty','filled_avg_price','status')}

    async def settle(self, abort=lambda:False, *, cancel=False):
        if not self.pending_id:
            return None
        order_id = self.pending_id
        deadline = time.monotonic()+8
        while True:
            order = await self.request('GET',f'orders/{order_id}')
            self.last_order = self.order_view(order)
            if order['status'] in TERMINAL:
                self.record('terminal', **self.last_order)
                self.pending_id = self.pending_client_id = None
                if order['status'] == 'rejected':
                    raise BrokerError('Alpaca PAPER order rejected. Review the paper dashboard.')
                return self.last_order
            if cancel or abort() or time.monotonic() >= deadline:
                response = await self.client.delete(PAPER_URL+f'/v2/orders/{order_id}',headers=self.headers)
                if response.status_code not in (204,404,422):
                    raise BrokerError('Paper-order cancellation was not confirmed. Review Alpaca before restarting.')
                # Bounded reconciliation after cancel; never assume a request canceled a fill.
                for _ in range(6):
                    await asyncio.sleep(.5)
                    order = await self.request('GET',f'orders/{order_id}')
                    self.last_order = self.order_view(order)
                    if order['status'] in TERMINAL:
                        self.record('terminal', **self.last_order)
                        self.pending_id = self.pending_client_id = None
                        return self.last_order
                raise BrokerError(f'Paper order {order_id} is unresolved. Check Alpaca; no new order will be sent.')
            await asyncio.sleep(.5)

    async def execute(self, symbol, signed_order, price, run_id, sequence, abort=lambda:False):
        if self.pending_id or self.pending_client_id:
            raise BrokerError('A previous paper order is unresolved; no new order will be sent.')
        state = await self.account(symbol)
        if signed_order == 0 or abort():
            return state
        if abs(signed_order)>20:
            raise BrokerError('Paper order exceeds the 20-share limit.')
        clock = await self.request('GET','clock')
        if not clock.get('is_open'):
            raise BrokerError('Market closed; no paper order submitted.')
        await self.check_open_orders(symbol)
        buy = signed_order > 0
        limit = (Decimal(str(price))*(Decimal('1.002') if buy else Decimal('.998'))).quantize(Decimal('.01'),rounding=ROUND_CEILING if buy else ROUND_FLOOR)
        if limit <= 0:
            raise BrokerError('Invalid paper limit price.')
        holdings = int(state['position'])
        room = max(0,int(Decimal(100)-Decimal(str(state['position']))))
        quantity = min(abs(signed_order), room, max(0,int(Decimal(str(state['cash']))/limit))) if buy else min(abs(signed_order),holdings)
        if not quantity:
            self.last_order = {'status':'skipped','symbol':symbol,'reason':'Cash or long-only holding limit','filled_qty':'0'}
            return await self.account(symbol)
        client_id = f'nq-{UUID(run_id).hex[:20]}-{sequence}'
        payload = {'symbol':symbol,'qty':str(quantity),'side':'buy' if buy else 'sell',
                   'type':'limit','limit_price':str(limit),'time_in_force':'day',
                   'extended_hours':False,'client_order_id':client_id}
        if abort():
            return state
        self.record('intent', **payload)
        self.pending_client_id = client_id
        try:
            order = await self.request('POST','orders',json=payload)
            self.pending_id = order['id']
            self.last_order = self.order_view(order)
            self.record('accepted', **self.last_order)
        except Exception as exc:
            # A timed-out POST could already be accepted: reconcile by GET, never POST again.
            raise BrokerError(f'Paper submission uncertain/failed. Review client order {client_id} in Alpaca; no automatic retry.') from exc
        await self.settle(abort)
        return await self.account(symbol)

    async def close(self):
        try:
            if self.pending_client_id and not self.pending_id:
                found = await self.request('GET','orders:by_client_order_id',
                                           params={'client_order_id':self.pending_client_id},allow_missing=True)
                if found:
                    self.pending_id = found['id']
                else:
                    raise BrokerError(f'Paper submission outcome unknown for {self.pending_client_id}. Review Alpaca before restarting.')
            if self.pending_id:
                await self.settle(cancel=True)
        finally:
            if self.owned_client:
                await self.client.aclose()
