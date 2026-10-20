import asyncio
import time
from unittest.mock import patch

import pytest

from backend.service import Controller, StartConfig
from nanoquant.model import Engine, Quote
from nanoquant.protocol import RESPONSE_BODY, crc16, decode
from nanoquant.transport import CommunicationError, Reply, SerialSession


class FakeSerial:
    def __init__(self, *, corrupt=None, chunk=20):
        self.engine = Engine()
        self.pending = b''
        self.writes = []
        self.closed = False
        self.corrupt = corrupt
        self.chunk = chunk

    def reset_input_buffer(self):
        self.pending = b''

    def write(self, packet):
        self.writes.append(packet)
        quote = decode(packet)
        order, position, killed = self.engine.step(quote)
        sequence = quote.sequence + (1 if self.corrupt == 'sequence' else 0)
        body = RESPONSE_BODY.pack(b'NR', 1, killed, sequence,
                                  order + (1 if self.corrupt == 'order' else 0), position, 1)
        self.pending = body + crc16(body).to_bytes(2, 'little')
        if self.corrupt == 'crc':
            self.pending = self.pending[:-1] + bytes([self.pending[-1] ^ 1])
        if self.corrupt == 'timeout':
            self.pending = b''
        return len(packet)

    def read(self, size):
        size = min(size, self.chunk)
        result, self.pending = self.pending[:size], self.pending[size:]
        return result

    def close(self):
        self.closed = True


def test_partial_packets_and_intertransaction_pause():
    fake = FakeSerial(chunk=3)
    with patch('nanoquant.transport.time.sleep') as sleep:
        session = SerialSession('COM_TEST', serial_factory=lambda *a, **k: fake)
        reply = session.transact(Quote(0, 9990, 30))
        assert (reply.order, reply.position, reply.engine_cycles) == (20, 20, 1)
        assert reply.host_round_trip_us >= 0
        assert sleep.call_args.args == (.002,)
        session.close()
    assert fake.closed


@pytest.mark.parametrize('failure', ['crc', 'timeout', 'sequence', 'order'])
def test_bad_response_never_retries(failure):
    fake = FakeSerial(corrupt=failure)
    with patch('nanoquant.transport.time.sleep'):
        session = SerialSession('COM_TEST', serial_factory=lambda *a, **k: fake)
        with pytest.raises(CommunicationError):
            session.transact(Quote(0, 9990, 20))
        with pytest.raises(CommunicationError, match='Session invalid'):
            session.transact(Quote(0, 9990, 20))
        session.close()
    assert len(fake.writes) == 1
    assert fake.closed


def test_live_reset_confirmation_required():
    async def scenario():
        controller = Controller()
        for config in (StartConfig(mode='fpga', port='COM6'),
                       StartConfig(mode='fpga', reset_confirmed=True)):
            with pytest.raises(ValueError, match='reset'):
                await controller.start('owner', config)
    asyncio.run(scenario())


def test_mock_live_stream_kill_and_close():
    fake = FakeSerial()
    async def scenario():
        with patch('nanoquant.transport.time.sleep'):
            controller = Controller(session_factory=lambda port: SerialSession(port, serial_factory=lambda *a, **k: fake))
            queue = controller.subscribe('owner')
            await controller.start('owner', StartConfig(mode='fpga', port='COM_TEST', reset_confirmed=True, speed=20))
            while True:
                message = await asyncio.wait_for(queue.get(), 2)
                if message['type'] == 'telemetry':
                    break
            assert message['mode'] == 'fpga'
            assert message['validation_status'] == 'matched'
            assert message['host_round_trip_us'] is not None
            controller.kill('owner')
            await asyncio.wait_for(controller.task, 2)
            assert controller.latest['killed']
            assert controller.reset_required
            assert controller.state == 'killed'
            assert fake.closed
    asyncio.run(scenario())


def test_stop_waits_for_inflight_reply_before_release():
    class SlowSession:
        closed = False
        def transact(self, quote):
            time.sleep(.03)
            assert not self.closed
            return Reply(quote.sequence, 0, 0, False, 1, 4500)
        def close(self):
            self.closed = True
    session = SlowSession()
    async def scenario():
        controller = Controller(session_factory=lambda port: session)
        await controller.start('owner', StartConfig(mode='fpga', port='test', reset_confirmed=True))
        await asyncio.sleep(.01)
        stop = asyncio.create_task(controller.stop('owner'))
        await asyncio.sleep(.001)
        with pytest.raises(ValueError, match='already owns'):
            await controller.start('other', StartConfig())
        await stop
        assert session.closed
        assert controller.owner is None
        assert controller.reset_required
    asyncio.run(scenario())


def test_live_timeout_stops_and_releases_port_on_disconnect():
    class BrokenSession:
        closed = False
        calls = 0
        def transact(self, quote):
            self.calls += 1
            raise CommunicationError('Timeout; physically reset FPGA')
        def close(self):
            self.closed = True
    session = BrokenSession()
    async def scenario():
        controller = Controller(session_factory=lambda port: session)
        controller.subscribe('owner')
        await controller.start('owner', StartConfig(mode='fpga', port='test', reset_confirmed=True))
        await controller.task
        assert controller.state == 'error'
        assert controller.reset_required
        assert 'reset' in controller.error
        await controller.disconnect('owner')
        assert session.closed
        assert session.calls == 1
    asyncio.run(scenario())


def test_port_busy_and_physical_disconnect_surface_errors():
    async def busy():
        def unavailable(port):
            raise OSError('Port is already open in another application')
        controller = Controller(session_factory=unavailable)
        await controller.start('owner', StartConfig(mode='fpga', port='test', reset_confirmed=True))
        await controller.task
        assert controller.state == 'error'
        assert 'another application' in controller.error
        assert controller.owner is None
        assert controller.reset_required
    asyncio.run(busy())
    fake = FakeSerial()
    with patch('nanoquant.transport.time.sleep'):
        session = SerialSession('test', serial_factory=lambda *a, **k: fake)
        with patch.object(fake, 'read', side_effect=OSError('USB disconnected')):
            with pytest.raises(CommunicationError, match='USB disconnected'):
                session.transact(Quote(0, 9990, 20))
        assert len(fake.writes) == 1
        session.close()


def test_owner_disconnect_closes_live_port():
    fake = FakeSerial()
    async def scenario():
        with patch('nanoquant.transport.time.sleep'):
            controller = Controller(session_factory=lambda port: SerialSession(port, serial_factory=lambda *a, **k: fake))
            queue = controller.subscribe('owner')
            await controller.start('owner', StartConfig(mode='fpga', port='test', reset_confirmed=True))
            while (await asyncio.wait_for(queue.get(), 2))['type'] != 'telemetry':
                pass
            await controller.disconnect('owner')
            assert fake.closed
            assert controller.state == 'stopped'
            assert controller.reset_required
    asyncio.run(scenario())


def test_pending_kill_is_not_discarded_by_stop():
    fake = FakeSerial()
    async def scenario():
        with patch('nanoquant.transport.time.sleep'):
            controller = Controller(session_factory=lambda port: SerialSession(port, serial_factory=lambda *a, **k: fake))
            controller.subscribe('owner')
            await controller.start('owner', StartConfig(mode='fpga', port='test', reset_confirmed=True))
            controller.kill('owner')
            assert controller.status()['kill_pending']
            await controller.stop('owner')
            assert controller.latest['killed']
            assert controller.state == 'killed'
            assert len(fake.writes) == 1
    asyncio.run(scenario())
