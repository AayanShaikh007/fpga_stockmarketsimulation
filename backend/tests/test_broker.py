import asyncio
from uuid import uuid4
from unittest.mock import patch

import httpx
import pytest
from backend.broker import AlpacaPaper, BrokerError
from backend.service import Controller, StartConfig


def setup_client(tmp_path, *, cash='100000', held='0', closed=False, timeout=False, existing=False, pending=False):
    calls=[]
    canceled=[]
    order={'id':'order-1','client_order_id':'test','symbol':'AAPL','qty':'20','side':'buy',
           'status':'new' if pending else 'filled','filled_qty':'0' if pending else '20','filled_avg_price':None if pending else '100'}
    def handle(req):
        assert req.url.host=='paper-api.alpaca.markets'
        calls.append((req.method,req.url.path))
        path=req.url.path.removeprefix('/v2/')
        if path=='account': return httpx.Response(200,json={'status':'ACTIVE','cash':cash,'equity':'100000','buying_power':'400000'})
        if path=='positions/AAPL': return httpx.Response(200,json={'qty':held,'market_value':'0','unrealized_pl':'0'})
        if path=='clock': return httpx.Response(200,json={'is_open':not closed})
        if path=='assets/AAPL': return httpx.Response(200,json={'status':'active','tradable':True})
        if path=='orders' and req.method=='GET': return httpx.Response(200,json=[order] if existing else [])
        if path=='orders' and req.method=='POST':
            import json
            payload=json.loads(req.content)
            assert int(payload['qty'])<=20
            assert payload['type']=='limit' and payload['extended_hours'] is False
            assert payload['limit_price']=='100.20'
            order.update(client_order_id=payload['client_order_id'],qty=payload['qty'],side=payload['side'])
            if timeout: raise httpx.ReadTimeout('test',request=req)
            return httpx.Response(200,json=order)
        if path=='orders:by_client_order_id': return httpx.Response(200,json=order)
        if path=='orders/order-1' and req.method=='DELETE':
            canceled.append(True);order['status']='canceled'
            return httpx.Response(204)
        if path=='orders/order-1': return httpx.Response(200,json=order)
        raise AssertionError((req.method,path))
    client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    with patch('backend.broker.credentials',return_value=('test','test-secret')):
        broker=AlpacaPaper(client=client,journal=tmp_path/'orders.jsonl')
    return broker,client,calls,canceled


def test_paper_only_submission_and_persistent_balance(tmp_path):
    async def scenario():
        broker,client,calls,_=setup_client(tmp_path)
        await broker.preflight('AAPL')
        result=await broker.execute('AAPL',20,100,str(uuid4()),0)
        assert result['cash']==100000 and result['equity']==100000
        assert result['last_order']['status']=='filled'
        assert calls.count(('POST','/v2/orders'))==1
        assert 'test-secret' not in (tmp_path/'orders.jsonl').read_text()
        await broker.close();await client.aclose()
    asyncio.run(scenario())


def test_no_shorting_or_margin_sizing(tmp_path):
    async def scenario():
        broker,client,calls,_=setup_client(tmp_path,cash='100',held='0')
        await broker.execute('AAPL',-20,100,str(uuid4()),0)
        await broker.execute('AAPL',20,100,str(uuid4()),1)
        assert not any(method=='POST' for method,_ in calls)
        await client.aclose()
    asyncio.run(scenario())


def test_fractional_existing_holding_preserves_100_share_limit(tmp_path):
    async def scenario():
        broker,client,calls,_=setup_client(tmp_path,held='99.5')
        await broker.execute('AAPL',20,100,str(uuid4()),0)
        assert not any(method=='POST' for method,_ in calls)
        await client.aclose()
    asyncio.run(scenario())


def test_closed_market_and_existing_orders_block_preflight(tmp_path):
    async def scenario():
        for options in ({'closed':True},{'existing':True}):
            broker,client,calls,_=setup_client(tmp_path,**options)
            with pytest.raises(BrokerError): await broker.preflight('AAPL')
            assert not any(method=='POST' for method,_ in calls)
            await client.aclose()
    asyncio.run(scenario())


def test_uncertain_post_is_never_resent(tmp_path):
    async def scenario():
        broker,client,calls,_=setup_client(tmp_path,timeout=True)
        with pytest.raises(BrokerError,match='uncertain'):
            await broker.execute('AAPL',20,100,str(uuid4()),0)
        with pytest.raises(BrokerError,match='unresolved'):
            await broker.execute('AAPL',20,100,str(uuid4()),1)
        await broker.close()
        assert calls.count(('POST','/v2/orders'))==1
        assert ('GET','/v2/orders:by_client_order_id') in calls
        await client.aclose()
    asyncio.run(scenario())


def test_pending_owned_order_canceled_on_close(tmp_path):
    async def scenario():
        broker,client,calls,canceled=setup_client(tmp_path,pending=True)
        broker.pending_id='order-1'
        broker.pending_client_id='owned'
        await broker.close()
        assert canceled and broker.pending_id is None
        assert broker.last_order['status']=='canceled'
        await client.aclose()
    asyncio.run(scenario())


def test_broker_mode_requires_live_feed_and_consent():
    async def scenario():
        for config in (StartConfig(execution='alpaca_paper'),StartConfig(execution='alpaca_paper',source='replay',paper_confirmed=True)):
            with pytest.raises(ValueError,match='PAPER'):
                await Controller().start('owner',config)
        with pytest.raises(ValueError): StartConfig(execution='live_money')
    asyncio.run(scenario())


def test_controller_streams_broker_equity_not_local_ledger():
    from backend.market import MarketSample
    from decimal import Decimal
    class Broker:
        snapshot={'environment':'alpaca_paper','cash':12345,'equity':12500}
        last_order=None
        closed=False
        async def preflight(self,symbol): pass
        async def execute(self,*args,**kwargs): return self.snapshot
        async def close(self): self.closed=True
    broker=Broker()
    async def feed(*args):
        yield MarketSample('AAPL',Decimal(100),10,'2026-10-21T14:00:00Z','alpaca_iex_live')
    async def scenario():
        with patch('backend.service.credentials'),patch('backend.service.AlpacaPaper',return_value=broker),patch('backend.service.live_samples',feed):
            controller=Controller()
            await controller.start('owner',StartConfig(source='live',execution='alpaca_paper',paper_confirmed=True))
            # Interrupt pacing after the first sample; no real broker calls occur.
            while controller.latest is None: await asyncio.sleep(.001)
            await controller.stop('owner')
        assert controller.latest['paper'] is None
        assert controller.latest['broker']['cash']==12345
        assert broker.closed
    asyncio.run(scenario())


def test_failed_broker_preflight_never_opens_uart():
    class Broker:
        snapshot=None
        last_order=None
        async def preflight(self,symbol): raise BrokerError('Market closed')
        async def close(self): pass
    async def scenario():
        with patch('backend.service.credentials'),patch('backend.service.AlpacaPaper',return_value=Broker()):
            with patch('backend.service.SerialSession') as serial:
                controller=Controller(session_factory=serial)
                await controller.start('owner',StartConfig(source='live',execution='alpaca_paper',paper_confirmed=True,mode='fpga',port='fake',reset_confirmed=True))
                await controller.task
                serial.assert_not_called()
        assert controller.state=='error' and controller.owner is None
    asyncio.run(scenario())
