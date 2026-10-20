from agents.usage import Usage
from atlas import gateway
from atlas.constants import COMPLETIONS
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route


class ModelProxy:
    """What stands where upstream's LiteLLM proxy stands: `LLM_BASE_URL`.

    It answers the harness's Chat Completions requests by asking the model
    through this repo's gateway, and keeps what they cost.

    Attributes:
        usage (Usage): what every answered request cost.
        conversation (list): the last request's messages and its answer,
            which is the transcript so far if the harness never returns.
    """

    def __init__(self, client):
        self.client = client
        self.usage = Usage()
        self.conversation: list = []

    def app(self) -> Starlette:
        """The proxy, as an ASGI app.

        Returns:
            Starlette: the app.
        """
        return Starlette(
            routes=[Route(COMPLETIONS, self.complete, methods=["POST"])])

    async def complete(self, request: Request) -> Response:
        """One model request, answered in Chat Completions form.

        A refusal is answered with the status the gateway gave, so the
        harness retries what it retries (`agent-eval.ts:214`).

        Args:
            request (Request): the harness's request.

        Returns:
            Response: the completion, or the error.
        """
        body = await request.json()
        model, messages = body.pop("model"), body.pop("messages")
        tools = body.pop("tools", [])
        try:
            response = await gateway.ask(self.client, model, messages, tools,
                                         body)
        except Exception as error:  # noqa: BLE001 -- answered to the harness
            status = 400 if isinstance(error, ValueError) else getattr(
                error, "status_code", None) or 500
            return JSONResponse(
                {
                    "error": {
                        "type": type(error).__name__,
                        "message": str(error)
                    }
                },
                status_code=status)
        self.usage.add(gateway.usage_of(response))
        answer = response.model_dump(mode="json", exclude_none=True)
        self.conversation = [*messages, answer["choices"][0]["message"]]
        return JSONResponse(answer)
