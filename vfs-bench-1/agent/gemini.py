import json
from typing import Any

import httpx

# Divergence: how a Gemini model is asked. Upstream sends every model one
# Chat Completions request per turn, a Gemini one through OpenRouter pinned
# to `google-vertex` or through Google's own OpenAI endpoint
# (`utils/api_model/model_provider.py`). The gateway's two OpenAI-style
# endpoints both damage a Gemini draw: they decode the backslash escapes
# inside a tool call's arguments, so a `\n` the model wrote in a Python
# string reached the tool as a line break and the script failed on it, and
# they ignore `reasoning_effort`, so every effort ran at Gemini's default.
# The gateway's native endpoint does neither, so a Gemini model is asked
# there, through LiteLLM's Gemini adapter, which makes the Chat Completions
# request the runner builds into Gemini's own. The model's name on the
# gateway is `google/<model>`, and `gemini/` picks the adapter.
GEMINI = "google/"

# The native endpoint reads only the camelCase spelling of these fields,
# where Google's own API reads either and LiteLLM writes the snake_case one;
# and it writes an unset field as null, where Google leaves it out and
# LiteLLM takes a null for a value. Neither rewrite changes what the model is
# sent or what it answered. A field the gateway cannot read it drops without
# a word -- a system message goes missing that way, and only its token count
# shows it -- so any other snake_case field fails the request rather than
# reaching the model as nothing.
CAMEL = {
    "system_instruction": "systemInstruction",
    "function_declarations": "functionDeclarations",
    "function_call": "functionCall",
    "function_response": "functionResponse",
    "max_output_tokens": "maxOutputTokens",
}


def _unset(node: Any) -> Any:
    """A native Gemini reply with every null field left out, as Google does.

    `args` is the model's own call and is kept whole: a null in it is a value
    the model chose, not an unset field.

    Args:
        node (Any): the parsed reply, or any part of it.

    Returns:
        Any: the same, without its null fields.
    """
    if isinstance(node, dict):
        return {
            key: value if key == "args" else _unset(value)
            for key, value in node.items() if value is not None
        }
    if isinstance(node, list):
        return [_unset(value) for value in node]
    return node


class NativeGemini(httpx.AsyncBaseTransport):
    """The gateway's native Gemini endpoint, spoken to as Google's is.

    Renames `CAMEL`'s fields in each request and drops the nulls from each
    reply, and passes everything else through as it is.
    """

    def __init__(self):
        self.inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self,
                                   request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)

        def spelled(node: dict) -> dict:
            for snake, camel in CAMEL.items():
                if snake in node:
                    node[camel] = node.pop(snake)
            unread = [key for key in node if "_" in key]
            if unread:
                raise ValueError(f"the gateway would drop {unread}")
            return node

        spelled(body)
        config = spelled(body.get("generationConfig") or {})
        spelled(config.get("thinkingConfig") or {})
        spelled(body.get("toolConfig") or {})
        for tool in body.get("tools", []):
            spelled(tool)
        for content in body.get("contents",
                                []) + [body.get("systemInstruction") or {}]:
            for part in spelled(content).get("parts", []):
                spelled(part)
        sent = json.dumps(body).encode()
        headers = request.headers.copy()
        headers["content-length"] = str(len(sent))
        # The extensions carry the client's timeout; a request rebuilt
        # without them waits on a stalled gateway for as long as the run
        # lasts.
        response = await self.inner.handle_async_request(
            httpx.Request(request.method,
                          request.url,
                          headers=headers,
                          content=sent,
                          extensions=request.extensions))
        received = await response.aread()
        try:
            received = json.dumps(_unset(json.loads(received))).encode()
        except ValueError:
            pass
        kept = [(key, value) for key, value in response.headers.items()
                if key.lower() not in ("content-encoding", "content-length",
                                       "transfer-encoding")]
        return httpx.Response(response.status_code,
                              headers=kept,
                              content=received)

    async def aclose(self):
        await self.inner.aclose()


def native_model(name: str, base_url: str, api_key: str, timeout, renamed):
    """A Gemini model on the gateway's native endpoint.

    Imported here: LiteLLM takes seconds to load, and only a Gemini draw
    needs it. On import it reads its model table from GitHub, as a proxy
    does on start; the table packed into the locked release predates
    gemini-3.8-flash and refuses its `reasoning_effort`, so an import that
    cannot reach GitHub fails the draw rather than changing it.

    Args:
        name (str): the gateway's model id, `google/<model>`.
        base_url (str): the gateway's OpenAI base URL, `.../v1`.
        api_key (str): the gateway key.
        timeout: what one request may take, as the OpenAI client's.
        renamed (type): the class that puts upstream's model wrapper on the
            model: its tool-name resolution on the replies, and its reading
            of a request refused as too long.

    Returns:
        tuple: the model, and the HTTP handler its requests go through,
            for `ModelSettings.extra_args["client"]`.
    """
    from agents.extensions.models.litellm_model import LitellmModel
    from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
    from pydantic_core import SchemaSerializer, core_schema

    class Handler(AsyncHTTPHandler):
        """The one client a run's requests go through, as its settings.

        The SDK hands a request's extra arguments to LiteLLM, and writes its
        settings out as JSON for the trace, where this is its name; a copy
        of the settings is still this client.
        """
        __pydantic_serializer__ = SchemaSerializer(
            core_schema.any_schema(
                serialization=core_schema.plain_serializer_function_ser_schema(
                    lambda _: "native Gemini")))

        def __deepcopy__(self, memo):
            return self

    handler = Handler()
    handler.client = httpx.AsyncClient(transport=NativeGemini(),
                                       timeout=timeout)

    class Model(renamed, LitellmModel):
        pass

    return Model(model=f"gemini/{name}", base_url=base_url,
                 api_key=api_key), handler
