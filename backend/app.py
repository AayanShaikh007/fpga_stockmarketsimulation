import asyncio
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from serial.tools.list_ports import comports

from .service import Controller, StartConfig

ORIGINS = {'http://localhost:5173', 'http://127.0.0.1:5173'}


def create_app():
    controller = Controller()

    @asynccontextmanager
    async def lifespan(app):
        yield
        if controller.owner:
            await controller.stop(controller.owner)

    app = FastAPI(title='NanoQuant local telemetry', lifespan=lifespan)
    app.state.controller = controller
    app.add_middleware(CORSMiddleware, allow_origins=list(ORIGINS), allow_methods=['GET'])

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
                except (ValueError, TypeError) as exc:
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
