import socket
import sys

import httpx

# Divergence: how a Claude model is asked. Upstream sends every model one
# Chat Completions request per turn, and a Claude one, on Anthropic's own key,
# to Anthropic's OpenAI-compatible endpoint (`CustomModelProviderAnthropic`,
# utils/api_model/model_provider.py). That endpoint refuses adaptive thinking,
# and its `reasoning_effort` does not reach the model as an effort: asked at
# `max`, Claude Haiku 5.5 answered a test question there in 381 tokens, where
# the Messages API thought for 3,858. So a Claude model is asked on the
# Messages API, through LiteLLM's Anthropic adapter, which makes the Chat
# Completions request the runner builds into Anthropic's own, and an effort
# into adaptive thinking at that effort. `anthropic/` picks the adapter.
CLAUDE = "anthropic/"


def keepalive_options() -> list:
    """TCP keep-alive as Anthropic's own SDK sets it on every connection.

    A request answered with no bytes until the whole reply is ready leaves
    its connection silent for as long as the model takes, and one turn that
    writes a long file at max effort takes over ten minutes. Twice a
    connection silent that long was dropped somewhere between here and
    Anthropic without either end being told, and the draw waited on it for
    hours. Probes keep it open, or close it within minutes when the other
    end is gone, as the SDK's `_DefaultAsyncHttpxClient` does: its values,
    except that macOS spells the idle time `TCP_KEEPALIVE`, which the SDK
    sets only where `TCP_KEEPINTVL` is missing and so leaves at two hours.
    """
    options = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, True)]
    if hasattr(socket, "TCP_KEEPINTVL"):
        options.append((socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 60))
    if hasattr(socket, "TCP_KEEPCNT"):
        options.append((socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5))
    if hasattr(socket, "TCP_KEEPIDLE"):
        options.append((socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60))
    elif sys.platform == "darwin":
        options.append(
            (socket.IPPROTO_TCP, getattr(socket, "TCP_KEEPALIVE", 0x10), 60))
    return options


def claude_model(name: str, base_url: str, api_key: str, timeout, renamed):
    """A Claude model on Anthropic's Messages API.

    Imported here, as the Gemini model is: LiteLLM takes seconds to load,
    and only these two draws need it.

    Args:
        name (str): the model, `anthropic/<model>`.
        base_url (str): Anthropic's API, `https://api.anthropic.com`.
        api_key (str): the Anthropic key.
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
                    lambda _: "Anthropic, TCP keep-alive")))

        def __deepcopy__(self, memo):
            return self

    handler = Handler()
    handler.client = httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(socket_options=keepalive_options()),
        timeout=timeout)

    class Model(renamed, LitellmModel):

        def _fix_tool_message_ordering(self, messages):
            """The history as upstream sends it, not as the SDK reorders it.

            The SDK splits a turn that called several tools into a turn per
            call, each followed by its result, and leaves the turn's thinking
            on the first. Upstream sends the turn whole and then its results,
            which is the order the SDK already writes them in and the one
            Anthropic reads: each call in the turn the model made it in.
            """
            return messages

    return Model(model=name, base_url=base_url, api_key=api_key), handler
