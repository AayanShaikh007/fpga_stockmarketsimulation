import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from backend.provider import MarketDataError, download_bars, live_samples
from backend.replay import DownloadRequest, download_dataset, read_dataset, replay_samples


@pytest.fixture(autouse=True)
def fake_credentials(monkeypatch):
    monkeypatch.setenv('ALPACA_API_KEY','test-key')
    monkeypatch.setenv('ALPACA_SECRET_KEY','test-secret')


def request():
    return DownloadRequest(symbol='AAPL',start='2026-01-05T14:30:00Z',end='2026-01-05T15:30:00Z')


def test_history_pagination_and_auth_headers():
    calls=[]
    def handler(req):
        calls.append(req)
        assert req.headers['APCA-API-KEY-ID']=='test-key'
        assert req.url.host=='data.alpaca.markets'
        assert req.url.params['feed']=='iex'
        page=1 if req.url.params.get('page_token') else 0
        return httpx.Response(200,json={'bars':{'AAPL':[{'t':f'2026-01-05T14:3{page}:00Z','c':200+page,'v':10}]},'next_page_token':None if page else 'p2'})
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            r=request()
            rows=await download_bars(r.symbol,r.start,r.end,r.timeframe,client=client)
            assert len(rows)==2
    asyncio.run(scenario())
    assert len(calls)==2


def test_provider_errors_never_include_secrets():
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(429))) as client:
            r=request()
            with pytest.raises(MarketDataError,match='429') as error:
                await download_bars(r.symbol,r.start,r.end,r.timeframe,client=client)
            assert 'test-secret' not in str(error.value)
    asyncio.run(scenario())


def test_download_replay_hash_and_path_validation(tmp_path,monkeypatch):
    monkeypatch.setattr('backend.replay.DATA_DIR',tmp_path)
    bars=[{'t':'2026-01-05T14:30:00Z','c':100,'v':100},{'t':'2026-01-05T14:31:00Z','c':101,'v':120}]
    async def scenario():
        with patch('backend.replay.download_bars',new=AsyncMock(return_value=bars)):
            info=await download_dataset(request())
        dataset=read_dataset(info['id'])
        values=[s async for s in replay_samples(dataset)]
        assert len(values)==2 and values[1].price==101
        path=tmp_path/f"{info['id']}.json"
        data=json.loads(path.read_text()); data['rows'][0]['price']='99'; path.write_text(json.dumps(data))
        with pytest.raises(ValueError,match='checksum'):
            read_dataset(info['id'])
    asyncio.run(scenario())
    with pytest.raises(ValueError,match='Invalid replay ID'):
        read_dataset('../.env')


def test_fixture_is_explicitly_synthetic():
    dataset=read_dataset('demo')
    assert dataset['symbol']=='DEMO'
    assert dataset['source']=='synthetic_fixture'
    assert len(dataset['rows'])==12


def test_invalid_date_ranges():
    for start,end in [('2026-01-06T00:00:00Z','2026-01-05T00:00:00Z'),('2026-01-05T00:00:00','2026-01-06T00:00:00')]:
        with pytest.raises(ValueError):
            DownloadRequest(symbol='AAPL',start=start,end=end)


def test_live_auth_subscription_and_deduplication():
    class Socket:
        def __init__(self): self.sent=[]
        async def send(self,value): self.sent.append(json.loads(value))
        async def recv(self): return '[{"T":"success","msg":"authenticated"}]'
        def __aiter__(self): return self.messages()
        async def messages(self):
            timestamp=datetime.now(timezone.utc).isoformat()
            trade={'T':'t','S':'AAPL','p':200,'s':20,'i':1,'t':timestamp}
            yield json.dumps([trade,trade])
            await asyncio.sleep(10)
    socket=Socket()
    class Connection:
        async def __aenter__(self): return socket
        async def __aexit__(self,*args): pass
    stats=dict(feed_samples_received=0,feed_samples_skipped=0,duplicate_feed_events=0,stale_feed_events=0)
    async def scenario():
        source=live_samples('AAPL',stats,connector=lambda *a,**k:Connection())
        sample=await asyncio.wait_for(anext(source),2)
        assert sample.symbol=='AAPL'
        await source.aclose()
    asyncio.run(scenario())
    assert socket.sent[0]['action']=='auth'
    assert socket.sent[1]=={'action':'subscribe','trades':['AAPL']}
    assert stats['duplicate_feed_events']==1
