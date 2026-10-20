import asyncio
import contextlib
import socket
from contextlib import AsyncExitStack

import uvicorn


class _Server(uvicorn.Server):
    """uvicorn, leaving this process's signals to it."""

    @contextlib.contextmanager
    def capture_signals(self):
        yield


async def listen(app, stack: AsyncExitStack, keep_alive: int = 5) -> str:
    """Serve `app` on an unused loopback port until `stack` closes.

    In this process's own loop, so what it serves can call back into
    whatever else this process is serving.

    Args:
        app: an ASGI app.
        stack (AsyncExitStack): stops the server.
        keep_alive (int): seconds an idle connection stays open; uvicorn's
            own 5 unless the caller needs longer.

    Returns:
        str: its address.
    """
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = _Server(
        uvicorn.Config(app,
                       log_level="warning",
                       timeout_graceful_shutdown=1,
                       timeout_keep_alive=keep_alive))
    serving = asyncio.create_task(server.serve(sockets=[sock]))

    async def stop():
        server.should_exit = True
        await serving

    stack.push_async_callback(stop)
    while not server.started:
        if serving.done():
            serving.result()
        await asyncio.sleep(.05)
    return f"http://127.0.0.1:{sock.getsockname()[1]}"
