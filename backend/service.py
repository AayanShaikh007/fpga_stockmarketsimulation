import asyncio
import time
from uuid import uuid4
from contextlib import suppress, aclosing
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from nanoquant.feed import generate
from nanoquant.model import Engine
from nanoquant.transport import SerialSession
from .telemetry import telemetry
from .market import MarketSample, Normalizer
from .paper import PaperPortfolio
from .performance import Performance
from .provider import credentials, live_samples
from .replay import read_dataset, replay_samples
from .broker import AlpacaPaper
from .strategies import Strategy, StrategyStore, StrategyEngine, BUILTIN, fpga_supported, digest


class StartConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['simulation', 'fpga'] = 'simulation'
    speed: float = Field(default=5, ge=1, le=20)
    seed: int = Field(default=1, ge=0, le=0xffffffff)
    port: str = Field(default='', max_length=128)
    reset_confirmed: bool = False
    source: Literal['generated', 'live', 'replay'] = 'generated'
    symbol: Literal['AAPL', 'NVDA', 'TSLA', 'DEMO'] = 'AAPL'
    replay_id: str = Field(default='demo', max_length=64)
    fee_bps: float = Field(default=1, ge=0, le=100)
    execution: Literal['local', 'alpaca_paper'] = 'local'
    paper_confirmed: bool = False
    strategy_snapshot_id:str | None = Field(default=None,pattern='^[a-f0-9]{32}$')


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
        self.performance = Performance()
        self.dataset = None
        self.broker_snapshot = None
        self.strategy_spec = BUILTIN
        self.strategy_snapshot = None

    def status(self):
        return dict(type='status', state=self.state, mode=self.config.mode,
                    run_id=self.run_id, owner=self.owner, speed=self.config.speed,
                    port=self.config.port, error=self.error,
                    kill_pending=self.kill_requested and self.state in ('running', 'stopping'),
                    reset_required=self.reset_required, latest=self.latest,
                    source=self.config.source, symbol=self.config.symbol,
                    replay_id=self.config.replay_id, performance=self.performance.snapshot(),
                    execution=self.config.execution, broker=self.broker_snapshot,
                    strategy_snapshot_id=self.config.strategy_snapshot_id,
                    strategy={'spec':self.strategy_spec.model_dump(),'sha256':digest(self.strategy_spec.model_dump())})

    def subscribe(self, client):
        queue = asyncio.Queue(maxsize=256)
        self.clients[client] = queue
        return queue

    def emit(self, message):
        for queue in self.clients.values():
            if queue.full():
                queue.get_nowait()
                self.performance.feed['observer_events_dropped'] += 1
            queue.put_nowait(message)

    async def start(self, client, config):
        if self.task is not None and not self.task.done():
            raise ValueError('A run already owns the engine. Stop it before starting another.')
        if config.mode == 'fpga' and (not config.port.strip() or not config.reset_confirmed):
            raise ValueError('Select a port and physically reset the FPGA, then confirm reset before every live run.')
        if config.execution == 'alpaca_paper' and (config.source != 'live' or not config.paper_confirmed):
            raise ValueError('Alpaca PAPER requires live stock data and explicit paper-order confirmation. Historical/generated runs stay local.')
        frozen = StrategyStore().snapshot(config.strategy_snapshot_id) if config.strategy_snapshot_id else None
        spec = Strategy(**frozen['spec']) if frozen else BUILTIN
        if config.mode == 'fpga' and not fpga_supported(spec):
            raise ValueError('This frozen strategy is Python-only. Current FPGA supports only anchor threshold=5, max_order=20, position_limit=100. No strategy upload protocol exists yet.')
        self.strategy_spec,self.strategy_snapshot=spec,frozen
        self.dataset = None
        self.broker_snapshot = None
        if config.source == 'live':
            if config.symbol == 'DEMO':
                raise ValueError('Select AAPL, NVDA, or TSLA for a live feed')
            credentials()
        elif config.source == 'replay':
            self.dataset = read_dataset(config.replay_id)
            config.symbol = self.dataset['symbol']
        self.performance = Performance()
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

    async def samples(self):
        if self.config.source == 'live':
            async with aclosing(live_samples(self.config.symbol, self.performance.feed)) as stream:
                async for sample in stream:
                    yield sample
        elif self.config.source == 'replay':
            async for sample in replay_samples(self.dataset):
                yield sample
        else:
            for quote in generate(count=2**32, seed=self.config.seed):
                yield MarketSample('NQ', Decimal(quote.price)/100, quote.quantity,
                                   datetime.now(timezone.utc).isoformat(), 'generated')

    async def run(self):
        engine = StrategyEngine(self.strategy_spec)
        mapper = Normalizer()
        if self.config.source == 'generated':
            mapper.anchor = Decimal(100)
        portfolio = PaperPortfolio(fee_bps=self.config.fee_bps)
        session = None
        broker = None
        source = self.samples()
        next_sample = None
        last_sample = None
        sequence = 0
        try:
            if self.config.execution == 'alpaca_paper':
                broker = AlpacaPaper()
                await broker.preflight(self.config.symbol)
                self.broker_snapshot = broker.snapshot
                self.emit(self.status())
            if self.config.mode == 'fpga':
                session = await asyncio.to_thread(self.session_factory, self.config.port)
            while sequence < 2**32:
                if self.stop_event.is_set() and not self.kill_requested:
                    break
                control_only = False
                if self.kill_requested:
                    sample = last_sample
                    control_only = sample is None
                    if sample is None:
                        sample = MarketSample(self.config.symbol, Decimal(100), 0,
                                              datetime.now(timezone.utc).isoformat(), 'control_only')
                else:
                    if next_sample is None:
                        next_sample = asyncio.create_task(anext(source))
                    # Polling the task does not cancel source reads. Stop/kill remains
                    # responsive even when a market is closed and no trades arrive.
                    done, _ = await asyncio.wait({next_sample}, timeout=.05)
                    if not done:
                        continue
                    try:
                        sample = next_sample.result()
                    except StopAsyncIteration:
                        self.state = 'completed'
                        break
                    next_sample = None
                    last_sample = sample
                quote = mapper.quote(sample, sequence, self.kill_requested)
                if session is not None:
                    reply = await asyncio.to_thread(session.transact, quote)
                    result = (reply.order, reply.position, reply.killed)
                    message = telemetry(quote, result, 'fpga', self.run_id,
                                        host_us=reply.host_round_trip_us, cycles=reply.engine_cycles,
                                        python_us=getattr(reply, 'python_compute_us', None))
                    self.performance.uart = dict(getattr(session, 'metrics', {}))
                else:
                    before = time.perf_counter_ns()
                    result = engine.step(quote)
                    message = telemetry(quote, result, 'simulation', self.run_id,
                                        python_us=(time.perf_counter_ns()-before)/1000)
                self.performance.observe(message)
                if broker is not None:
                    self.broker_snapshot = await broker.execute(self.config.symbol, result[0], sample.price,
                        self.run_id, sequence, abort=lambda:self.stop_event.is_set() or self.kill_requested)
                    paper = None
                else:
                    paper = portfolio.apply(result[0], sample.price)
                message.update({
                    'symbol': sample.symbol, 'data_source': sample.source,
                    'market_timestamp': None if control_only else sample.timestamp,
                    'price_usd': None if control_only else float(sample.price),
                    'anchor_usd': None if control_only else float(mapper.anchor),
                    'input_quantity': sample.quantity, 'control_only': control_only,
                    'normalization': 'fixed-anchor basis points; 10000 = anchor',
                    'paper': paper, 'performance': self.performance.snapshot(),
                    'execution':self.config.execution,'broker':self.broker_snapshot,
                    'strategy':{'name':self.strategy_spec.name,'sha256':digest(self.strategy_spec.model_dump()),
                                'snapshot_id':self.config.strategy_snapshot_id},
                    'risk_checks': {'max_order':self.strategy_spec.max_order,'position_limit':self.strategy_spec.position_limit,
                                    'position_before':result[1]-result[0],
                                    'position_after':result[1],
                                    'order_within_limit':abs(result[0])<=self.strategy_spec.max_order,
                                    'position_within_limit':abs(result[1])<=self.strategy_spec.position_limit},
                })
                self.latest = message
                self.emit(message)
                sequence += 1
                if result[2]:
                    self.state = 'killed'
                    break
                self.wake.clear()
                if self.kill_requested or self.stop_event.is_set():
                    continue
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=max(5,1/self.config.speed) if broker else 1/self.config.speed)
                except asyncio.TimeoutError:
                    pass
        except Exception as exc:
            if session is not None:
                self.performance.uart = dict(getattr(session, 'metrics', {}))
            self.error, self.state = str(exc), 'error'
        finally:
            if broker is not None:
                try:
                    await broker.close()
                except Exception as exc:
                    self.error, self.state = str(exc), 'error'
                self.broker_snapshot = dict(broker.snapshot or {}) | {'last_order':broker.last_order}
            if next_sample is not None:
                next_sample.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await next_sample
            try:
                await source.aclose()
            except Exception as exc:
                self.error, self.state = f'Market source close failed: {exc}', 'error'
            if session is not None:
                try:
                    await asyncio.to_thread(session.close)
                except Exception as exc:
                    self.error, self.state = f'UART close failed: {exc}', 'error'
            if self.state in ('running', 'stopping'):
                self.state = 'stopped'
            self.owner = None
            self.emit(self.status())
