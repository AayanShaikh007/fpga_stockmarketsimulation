import asyncio
import time
from dataclasses import replace
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from nanoquant.feed import generate
from nanoquant.model import Engine
from nanoquant.transport import SerialSession
from .telemetry import telemetry


class StartConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['simulation', 'fpga'] = 'simulation'
    speed: float = Field(default=5, ge=1, le=20)
    seed: int = Field(default=1, ge=0, le=0xffffffff)
    port: str = Field(default='', max_length=128)
    reset_confirmed: bool = False


class Controller:
    """One run per process; a websocket owns it until stop or disconnect."""
    def __init__(self, session_factory=SerialSession):
        self.session_factory = session_factory
        self.clients = {}
        self.task = None
        self.owner = None
        self.config = StartConfig()
        self.run_id = None
        self.state = 'idle'
        self.error = None
        self.latest = None
        self.stop_event = asyncio.Event()
        self.wake = asyncio.Event()
        self.kill_requested = False
        self.reset_required = False

    def status(self):
        return dict(type='status', state=self.state, mode=self.config.mode,
                    run_id=self.run_id, owner=self.owner, speed=self.config.speed,
                    port=self.config.port, error=self.error,
                    kill_pending=self.kill_requested and self.state in ('running', 'stopping'),
                    reset_required=self.reset_required, latest=self.latest)

    def subscribe(self, client):
        queue = asyncio.Queue(maxsize=256)
        self.clients[client] = queue
        return queue

    def emit(self, message):
        for queue in self.clients.values():
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(message)

    async def start(self, client, config):
        if self.task is not None and not self.task.done():
            raise ValueError('A run already owns the engine. Stop it before starting another.')
        if config.mode == 'fpga' and (not config.port.strip() or not config.reset_confirmed):
            raise ValueError('Select a port and physically reset the FPGA, then confirm reset before every live run.')
        self.owner, self.config = client, config
        self.run_id, self.latest, self.error = str(uuid4()), None, None
        self.stop_event.clear()
        self.wake.clear()
        self.kill_requested = False
        self.state = 'running'
        if config.mode == 'fpga':
            self.reset_required = True
        self.emit(self.status())
        self.task = asyncio.create_task(self.run())

    def require_owner(self, client):
        if self.owner != client or self.task is None or self.task.done():
            raise ValueError('Only the active run owner can control this run.')

    async def stop(self, client):
        self.require_owner(client)
        self.state = 'stopping'
        self.stop_event.set()
        self.wake.set()
        self.emit(self.status())
        await self.task

    def kill(self, client):
        self.require_owner(client)
        self.kill_requested = True
        self.wake.set()
        self.emit(self.status())

    def speed(self, client, value):
        self.require_owner(client)
        self.config.speed = StartConfig(speed=value).speed
        self.wake.set()
        self.emit(self.status())

    async def disconnect(self, client):
        self.clients.pop(client, None)
        if self.owner == client and self.task is not None and not self.task.done():
            await self.stop(client)

    async def run(self):
        engine = Engine()
        session = None
        try:
            if self.config.mode == 'fpga':
                session = await asyncio.to_thread(self.session_factory, self.config.port)
            for quote in generate(count=2**32, seed=self.config.seed):
                if self.stop_event.is_set() and not self.kill_requested:
                    break
                if self.kill_requested:
                    quote = replace(quote, kill=True)
                if session is not None:
                    reply = await asyncio.to_thread(session.transact, quote)
                    result = (reply.order, reply.position, reply.killed)
                    message = telemetry(quote, result, 'fpga', self.run_id,
                                        host_us=reply.host_round_trip_us, cycles=reply.engine_cycles)
                else:
                    before = time.perf_counter_ns()
                    result = engine.step(quote)
                    message = telemetry(quote, result, 'simulation', self.run_id,
                                        python_us=(time.perf_counter_ns()-before)/1000)
                self.latest = message
                self.emit(message)
                if result[2]:
                    self.state = 'killed'
                    break
                self.wake.clear()
                if self.kill_requested or self.stop_event.is_set():
                    continue
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=1/self.config.speed)
                except asyncio.TimeoutError:
                    pass
        except Exception as exc:
            self.error, self.state = str(exc), 'error'
        finally:
            if session is not None:
                try:
                    await asyncio.to_thread(session.close)
                except Exception as exc:
                    self.error, self.state = f'UART close failed: {exc}', 'error'
            if self.state in ('running', 'stopping'):
                self.state = 'stopped'
            self.owner = None
            self.emit(self.status())
