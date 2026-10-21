import asyncio
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.market import MarketSample
from backend.provider import MarketDataError
from backend.service import Controller, StartConfig
from backend.tests.test_transport import FakeSerial
from nanoquant.transport import CommunicationError, SerialSession
from nanoquant.model import Quote


def test_replay_completes_with_paper_and_provenance():
    async def scenario():
        controller=Controller()
        queue=controller.subscribe('owner')
        await controller.start('owner',StartConfig(source='replay',speed=20))
        await asyncio.wait_for(controller.task,4)
        rows=[]
        while not queue.empty():
            row=queue.get_nowait()
            if row['type']=='telemetry': rows.append(row)
        assert len(rows)==12
        assert controller.state=='completed'
        assert rows[0]['price']==10000
        assert rows[1]['price']==9990
        assert rows[1]['decision']=='BUY'
        assert rows[1]['symbol']=='DEMO' and rows[1]['data_source']=='synthetic_fixture'
        assert rows[1]['paper']['filled_order']==15
        assert rows[-1]['host_round_trip_us'] is None
        assert rows[-1]['performance']['uart'] is None
        assert rows[-1]['risk_checks']['position_within_limit']
    asyncio.run(scenario())


def test_actual_wire_mapping_for_replay_via_fake_hardware():
    fake=FakeSerial()
    async def scenario():
        with patch('nanoquant.transport.time.sleep'):
            controller=Controller(session_factory=lambda port:SerialSession(port,serial_factory=lambda *a,**k:fake))
            await controller.start('owner',StartConfig(mode='fpga',port='fake',reset_confirmed=True,source='replay',speed=20))
            await asyncio.wait_for(controller.task,4)
        assert len(fake.writes)==12
        assert controller.latest['validation_status']=='matched'
        assert controller.latest['performance']['uart']['validated_replies']==12
        assert controller.latest['python_compute_us'] is not None
        assert controller.reset_required and fake.closed
    asyncio.run(scenario())


def test_waiting_live_source_can_be_killed_without_any_market_print():
    closed=[]
    async def blocked(symbol,stats):
        try:
            await asyncio.sleep(30)
            yield MarketSample(symbol,Decimal(100),1,'2026-01-01T00:00:00Z','test')
        finally:
            closed.append(True)
    async def scenario():
        with patch('backend.service.credentials',return_value=('a','b')), patch('backend.service.live_samples',blocked):
            controller=Controller()
            await controller.start('owner',StartConfig(source='live'))
            await asyncio.sleep(.02)
            controller.kill('owner')
            await asyncio.wait_for(controller.task,1)
        assert controller.latest['control_only']
        assert controller.latest['price_usd'] is None
        assert controller.latest['killed']
        assert closed
    asyncio.run(scenario())


def test_live_source_failure_closes_uart_and_releases_ownership():
    fake=FakeSerial()
    async def broken(symbol,stats):
        raise MarketDataError('Test market stream failure')
        yield
    async def scenario():
        with patch('backend.service.credentials',return_value=('a','b')), patch('backend.service.live_samples',broken), patch('nanoquant.transport.time.sleep'):
            controller=Controller(session_factory=lambda port:SerialSession(port,serial_factory=lambda *a,**k:fake))
            await controller.start('owner',StartConfig(source='live',mode='fpga',port='fake',reset_confirmed=True))
            await asyncio.wait_for(controller.task,1)
        assert controller.state=='error'
        assert 'stream failure' in controller.error
        assert controller.owner is None
        assert fake.closed and len(fake.writes)==0
    asyncio.run(scenario())


def test_missing_credentials_are_command_error_not_generated_fallback():
    with patch('backend.service.credentials',side_effect=MarketDataError('Configure credentials')):
        with TestClient(create_app()) as client:
            with client.websocket_connect('/ws') as ws:
                ws.receive_json()
                ws.send_json({'command':'start','config':{'source':'live'}})
                event=ws.receive_json()
                assert event['type']=='command_error'
                assert 'Configure credentials' in event['message']
                assert client.get('/api/status').json()['state']=='idle'


@pytest.mark.parametrize('failure,counter',[('crc','crc_errors'),('timeout','timeouts'),('sequence','sequence_errors'),('order','reference_errors')])
def test_uart_error_counters(failure,counter):
    fake=FakeSerial(corrupt=failure)
    with patch('nanoquant.transport.time.sleep'):
        session=SerialSession('fake',serial_factory=lambda *a,**k:fake)
        with pytest.raises(CommunicationError): session.transact(Quote(0,9990,20))
        assert session.metrics[counter]==1
        assert session.metrics['requests_sent']==1
        assert session.metrics['validated_replies']==0
        session.close()


def test_replay_routes_and_bad_id():
    with TestClient(create_app()) as client:
        assert client.get('/api/replays').json()[0]['source']=='synthetic_fixture'
        assert 'configured' in client.get('/api/provider').json()
        response=client.post('/api/replays/download',json={'symbol':'BAD'})
        assert response.status_code==422
        with client.websocket_connect('/ws') as ws:
            ws.receive_json()
            ws.send_json({'command':'start','config':{'source':'replay','replay_id':'../.env'}})
            assert ws.receive_json()['type']=='command_error'
