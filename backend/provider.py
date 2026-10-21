"""Alpaca market-data-only REST and WebSocket clients. No order API exists here."""
import asyncio
import json
import os
from collections import deque
from pathlib import Path

import httpx
from dotenv import load_dotenv
from websockets.asyncio.client import connect

from .market import SYMBOLS, alpaca_trade, is_stale


class MarketDataError(RuntimeError):
    pass


def credentials():
    load_dotenv(Path(__file__).parent / '.env', override=False)
    key, secret = os.getenv('ALPACA_API_KEY', ''), os.getenv('ALPACA_SECRET_KEY', '')
    if not key or not secret:
        raise MarketDataError('Configure ALPACA_API_KEY and ALPACA_SECRET_KEY in backend/.env. No generated-data fallback is used.')
    return key, secret


def provider_status():
    try:
        credentials()
        configured = True
    except MarketDataError:
        configured = False
    return {'provider': 'Alpaca', 'feed': 'IEX', 'configured': configured,
            'coverage': 'Single-exchange IEX trade prints; not consolidated market coverage',
            'symbols': list(SYMBOLS)}


async def download_bars(symbol, start, end, timeframe, *, client=None):
    key, secret = credentials()
    owned = client is None
    client = client or httpx.AsyncClient(timeout=20)
    params = dict(symbols=symbol, start=start.isoformat(), end=end.isoformat(),
                  timeframe=timeframe, feed='iex', adjustment='raw', sort='asc', limit=1000)
    rows, seen_tokens = [], set()
    try:
        while True:
            response = await client.get('https://data.alpaca.markets/v2/stocks/bars', params=params,
                                        headers={'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':secret})
            if response.status_code != 200:
                raise MarketDataError(f'Alpaca historical data HTTP {response.status_code}. Check credentials, entitlement, dates, or rate limits.')
            payload = response.json()
            rows.extend((payload.get('bars') or {}).get(symbol, []))
            token = payload.get('next_page_token')
            if len(rows) > 20000:
                raise MarketDataError('Replay exceeds 20,000 bars. Choose a shorter range.')
            if not token:
                break
            if token in seen_tokens:
                raise MarketDataError('Provider repeated a pagination token.')
            seen_tokens.add(token)
            params['page_token'] = token
        if not rows:
            raise MarketDataError('No historical bars returned for that range/feed.')
        return rows
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise MarketDataError('Historical market-data request failed; no replay was saved.') from exc
    finally:
        if owned:
            await client.aclose()


async def live_samples(symbol, stats, *, connector=connect):
    """Sample latest print at engine pace, counting superseded feed events.

    A bounded queue separates market bursts from stop-and-wait UART. No provider
    reconnect or replay of missed events occurs automatically.
    """
    key, secret = credentials()
    queue = asyncio.Queue(maxsize=1)

    def put(value):
        if queue.full():
            queue.get_nowait()
            stats['feed_samples_skipped'] += 1
        queue.put_nowait(value)

    async def receive():
        recent = deque()
        ids = set()
        last_timestamp = None
        try:
            async with connector('wss://stream.data.alpaca.markets/v2/iex', max_size=1048576,
                                 ping_interval=20, ping_timeout=20, open_timeout=10) as ws:
                await ws.send(json.dumps({'action':'auth','key':key,'secret':secret}))
                authenticated = False
                while not authenticated:
                    events = json.loads(await asyncio.wait_for(ws.recv(), 10))
                    for event in events:
                        if event.get('T') == 'error':
                            raise MarketDataError(f"Alpaca stream authentication failed (code {event.get('code')}).")
                        authenticated |= event.get('T') == 'success' and event.get('msg') == 'authenticated'
                await ws.send(json.dumps({'action':'subscribe','trades':[symbol]}))
                async for packet in ws:
                    for event in json.loads(packet):
                        if event.get('T') == 'error':
                            raise MarketDataError(f"Alpaca stream error (code {event.get('code')}); stopped without reconnecting.")
                        if event.get('T') != 't':
                            continue
                        sample = alpaca_trade(event, symbol)
                        stats['feed_samples_received'] += 1
                        if sample.event_id in ids:
                            stats['duplicate_feed_events'] += 1
                            continue
                        from datetime import datetime
                        stamp = datetime.fromisoformat(sample.timestamp.replace('Z', '+00:00'))
                        if is_stale(sample) or (last_timestamp is not None and stamp < last_timestamp):
                            stats['stale_feed_events'] += 1
                            continue
                        last_timestamp = stamp
                        ids.add(sample.event_id)
                        recent.append(sample.event_id)
                        if len(recent) > 2048:
                            ids.remove(recent.popleft())
                        put(sample)
                raise MarketDataError('Market stream closed. Start a fresh run; no automatic reconnect was attempted.')
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Never surface provider frames or credential-bearing request objects.
            put(exc if isinstance(exc, MarketDataError) else MarketDataError('Market stream failed; check network and provider access.'))

    task = asyncio.create_task(receive())
    try:
        while True:
            value = await queue.get()
            if isinstance(value, Exception):
                raise value
            yield value
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
