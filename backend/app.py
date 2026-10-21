import asyncio
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from serial.tools.list_ports import comports

from .service import Controller, StartConfig
from .provider import MarketDataError, provider_status
from .replay import DownloadRequest, download_dataset, list_datasets
from .broker import AlpacaPaper, BrokerError

ORIGINS = {'http://localhost:5173', 'http://127.0.0.1:5173'}


def create_app():
    controller = Controller()
    download_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        yield
        if controller.owner:
            await controller.stop(controller.owner)

    app = FastAPI(title='NanoQuant local telemetry', lifespan=lifespan)
    app.state.controller = controller
    app.add_middleware(CORSMiddleware, allow_origins=list(ORIGINS), allow_methods=['GET','POST'], allow_headers=['Content-Type'])

    @app.get('/api/provider')
    async def provider():
        return provider_status()

    @app.get('/api/paper-account')
    async def paper_account(symbol: str = 'AAPL'):
        broker = None
        try:
            broker = AlpacaPaper()
            return await broker.account(symbol)
        except (BrokerError, MarketDataError) as exc:
            raise HTTPException(400,str(exc)) from exc
        finally:
            if broker:
                await broker.close()

    @app.get('/api/replays')
    async def replays():
        return await asyncio.to_thread(list_datasets)

    @app.post('/api/replays/download')
    async def download(body: DownloadRequest, request: Request):
        if request.headers.get('origin') not in ORIGINS | {None}:
            raise HTTPException(403, 'Origin not allowed')
        if download_lock.locked():
            raise HTTPException(409, 'A historical download is already in progress')
        try:
            async with download_lock:
                return await download_dataset(body)
        except MarketDataError as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get('/api/status')
    async def status():
        return controller.status()

    @app.get('/api/ports')
    async def ports():
        found = await asyncio.to_thread(comports)
        return [{'device': p.device, 'description': p.description, 'hwid': p.hwid} for p in found]

    @app.websocket('/ws')
    async def stream(socket: WebSocket):
        if socket.headers.get('origin') not in ORIGINS | {None}:
            await socket.close(code=1008)
            return
        await socket.accept()
        client = str(uuid4())
        queue = controller.subscribe(client)
        await socket.send_json({'type': 'hello', 'client_id': client, 'status': controller.status()})

        async def sender():
            while True:
                await socket.send_json(await queue.get())

        send_task = asyncio.create_task(sender())
        try:
            while True:
                message = await socket.receive_json()
                try:
                    if not isinstance(message, dict):
                        raise ValueError('Command must be an object.')
                    command = message.get('command')
                    if command == 'start':
                        await controller.start(client, StartConfig(**message.get('config', {})))
                    elif command == 'stop':
                        await controller.stop(client)
                    elif command == 'kill':
                        controller.kill(client)
                    elif command == 'speed':
                        controller.speed(client, message.get('speed'))
                    else:
                        raise ValueError('Unknown command.')
                except (ValueError, TypeError, MarketDataError) as exc:
                    queue.put_nowait({'type': 'command_error', 'message': str(exc)})
        except (WebSocketDisconnect, ValueError, RuntimeError):
            pass
        finally:
            send_task.cancel()
            with suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                await send_task
            await controller.disconnect(client)

    return app


app = create_app()
