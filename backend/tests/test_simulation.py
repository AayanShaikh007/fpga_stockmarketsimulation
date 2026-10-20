import asyncio
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.service import Controller, StartConfig
from backend.telemetry import telemetry
from nanoquant.model import Quote


def receive_type(ws, kind):
    for _ in range(100):
        message = ws.receive_json()
        if message['type'] == kind:
            return message
    raise AssertionError(f'No {kind} received')


def test_simulation_websocket_and_kill():
    with TestClient(create_app()) as client:
        with client.websocket_connect('/ws') as ws:
            assert ws.receive_json()['type'] == 'hello'
            ws.send_json({'command': 'start', 'config': {'speed': 20}})
            row = receive_type(ws, 'telemetry')
            assert (row['price'], row['quantity'], row['order'], row['position']) == (9999, 7, 0, 0)
            assert row['mode'] == 'simulation'
            assert row['validation_status'] == 'reference'
            assert row['host_round_trip_us'] is None
            assert row['engine_cycles'] is None
            ws.send_json({'command': 'kill'})
            while True:
                row = receive_type(ws, 'telemetry')
                if row['killed']:
                    break
            assert row['decision'] == 'KILL'
            assert row['order'] == 0


def test_owner_conflict_and_disconnect_cleanup():
    app = create_app()
    with TestClient(app) as client:
        with client.websocket_connect('/ws') as observer:
            observer.receive_json()
            with client.websocket_connect('/ws') as owner:
                owner.receive_json()
                owner.send_json({'command': 'start', 'config': {}})
                receive_type(owner, 'telemetry')
                observer.send_json({'command': 'start', 'config': {}})
                assert 'already owns' in receive_type(observer, 'command_error')['message']
                observer.send_json({'command': 'stop'})
                assert 'owner' in receive_type(observer, 'command_error')['message']
            while True:
                state = receive_type(observer, 'status')
                if state['state'] == 'stopped':
                    break
            assert state['owner'] is None


def test_speed_stop_and_restart():
    async def scenario():
        controller = Controller()
        await controller.start('a', StartConfig(speed=20))
        await asyncio.sleep(.01)
        controller.speed('a', 2)
        assert controller.config.speed == 2
        await controller.stop('a')
        assert controller.state == 'stopped'
        await controller.start('b', StartConfig())
        await controller.stop('b')
    asyncio.run(scenario())


def test_config_validation():
    for options in ({'speed': 0}, {'speed': 21}, {'seed': -1}, {'mode': 'fake'}):
        with pytest.raises(ValueError):
            StartConfig(**options)


def test_mapping_keeps_physical_estimate_distinct():
    row = telemetry(Quote(42, 10010, 9), (-9, -9, 0), 'fpga', 'run', host_us=4300, cycles=1)
    assert row['decision'] == 'SELL'
    assert row['host_round_trip_us'] == 4300
    assert row['python_compute_us'] is None
    assert row['estimated_engine_ns'] == pytest.approx(37.037037)


def test_rejects_unknown_websocket_origin():
    with TestClient(create_app()) as client:
        with pytest.raises(Exception):
            with client.websocket_connect('/ws', headers={'origin': 'https://untrusted.example'}):
                pass
