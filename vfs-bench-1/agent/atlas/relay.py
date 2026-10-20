import json
import time

import httpx
from atlas.constants import CALL_TOOL
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route


class Relay:
    """What the harness is given as `MCP_SANDBOX_URL`: the app, relayed.

    Every request passes to the app and every answer back, byte for byte;
    a tool call is timed on the way, and its answer kept.

    Attributes:
        calls (list): each tool call the app was asked for, in order, with
            how long it took to answer and what it answered.
    """

    def __init__(self, sandbox: str):
        # Each call on a connection of its own. The app is uvicorn, which
        # closes a connection idle for its default 5 s, and a call sent on a
        # pooled one as it closed came back `Server disconnected without
        # sending a response.`, which the model read as the tool's answer.
        # A pool that let go at 4 s, as the harness's own `fetch` does, still
        # lost that race whenever the answer reached this process a second
        # late, through Docker's port forwarding or a busy event loop.
        self.sandbox = httpx.AsyncClient(
            base_url=sandbox,
            timeout=None,
            limits=httpx.Limits(max_keepalive_connections=0))
        self.calls: list = []

    def app(self) -> Starlette:
        """The relay, as an ASGI app.

        Returns:
            Starlette: the app.
        """
        return Starlette(routes=[
            Route("/{path:path}", self.forward, methods=["GET", "POST"])
        ])

    async def forward(self, request: Request) -> Response:
        """One request of the harness's for the app, passed on as it is.

        Args:
            request (Request): the harness's request.

        Returns:
            Response: the app's answer.
        """
        body = await request.body()
        call = None
        if request.url.path == CALL_TOOL:
            call = {"name": json.loads(body).get("tool_name"), "seconds": None}
            self.calls.append(call)
        began = time.monotonic()
        try:
            answer = await self.sandbox.request(request.method,
                                                request.url.path,
                                                content=body,
                                                headers={
                                                    "content-type":
                                                    request.headers.get(
                                                        "content-type",
                                                        "application/json")
                                                })
        except httpx.HTTPError as error:
            return Response(str(error), status_code=502)
        if call is not None:
            call["seconds"] = round(time.monotonic() - began, 3)
            call["answer"] = {
                "status": answer.status_code,
                "body": answer.text
            }
        return Response(answer.content,
                        status_code=answer.status_code,
                        media_type=answer.headers.get("content-type"))

    async def close(self):
        """Close the relay's connections to the app."""
        await self.sandbox.aclose()
