import json
from typing import Any

import httpx
from agents.usage import OutputTokensDetails, Usage
from atlas.constants import (ANTHROPIC, CAMEL, CUT, GEMINI, OPENAI,
                             RESPONSES_PARAMETERS)
from openai.types.chat import (ChatCompletion, ChatCompletionMessage,
                               ChatCompletionMessageToolCall)
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_tool_call import Function
from openai.types.completion_usage import (CompletionTokensDetails,
                                           CompletionUsage,
                                           PromptTokensDetails)


async def ask(client, model: str, messages: list, tools: list, extra: dict):
    """One model request, asked the way this repo's gateway needs it asked.

    An OpenAI model on the Responses endpoint, a Gemini model through
    LiteLLM's adapter and a Claude model through LiteLLM's on Anthropic's
    API, as `constants` declares; any other model on the gateway's Chat
    Completions endpoint, as the harness sent it.

    Args:
        client: the AsyncOpenAI client, for the gateway.
        model (str): the gateway's model id.
        messages (list): the conversation so far.
        tools (list): the tool definitions, as the harness sends them.
        extra (dict): the request's other parameters.

    Returns:
        The reply, in Chat Completions form.
    """
    if model.startswith(GEMINI):
        return await ask_gemini(client, model, messages, tools, extra)
    if model.startswith(OPENAI):
        return await ask_openai(client, model, messages, tools, extra)
    if model.startswith(ANTHROPIC):
        return await ask_anthropic(client, model, messages, tools, extra)
    return await client.chat.completions.create(model=model,
                                                messages=messages,
                                                tools=tools,
                                                **extra)


def usage_of(response) -> Usage:
    """One response's cost, as the accumulator the dump is written from.

    Args:
        response: a Chat Completions response.

    Returns:
        Usage: a single-request usage entry.
    """
    counted: CompletionUsage | None = getattr(response, "usage", None)
    details = getattr(counted, "completion_tokens_details", None)
    return Usage(
        requests=1,
        input_tokens=getattr(counted, "prompt_tokens", 0) or 0,
        output_tokens=getattr(counted, "completion_tokens", 0) or 0,
        output_tokens_details=OutputTokensDetails(
            reasoning_tokens=getattr(details, "reasoning_tokens", 0) or 0),
        total_tokens=getattr(counted, "total_tokens", 0) or 0)


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


class GeminiTransport(httpx.AsyncBaseTransport):
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
        response = await self.inner.handle_async_request(
            httpx.Request(request.method,
                          request.url,
                          headers=headers,
                          content=sent))
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


async def ask_gemini(client, model: str, messages: list, tools: list,
                     extra: dict):
    """One request through LiteLLM's Gemini adapter, as upstream's proxy.

    Args:
        client: the AsyncOpenAI client, for the gateway's address and key.
        model (str): the gateway's model id, `google/<model>`.
        messages (list): the conversation so far.
        tools (list): the tool definitions, as the harness sends them.
        extra (dict): extra request parameters.

    Returns:
        The response, in Chat Completions form.
    """
    # Imported here: it takes seconds, and only a Gemini draw needs it. On
    # import it reads its model table from GitHub, as a proxy does on start;
    # the table packed into the locked release predates gemini-3.8-flash and
    # refuses its `reasoning_effort`, so an import that cannot reach GitHub
    # fails the draw rather than changing it.
    import litellm
    from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler

    handler = AsyncHTTPHandler()
    handler.client = httpx.AsyncClient(transport=GeminiTransport(),
                                       timeout=client.timeout)
    try:
        return await litellm.acompletion(
            # `gemini/` picks LiteLLM's adapter and the rest is the gateway's
            # own id, `google/...`: it has no provider for the bare name.
            model=f"gemini/{model}",
            api_base=str(client.base_url).rstrip("/"),
            api_key=client.api_key,
            messages=messages,
            tools=tools,
            client=handler,
            **extra)
    finally:
        await handler.client.aclose()


async def ask_anthropic(client, model: str, messages: list, tools: list,
                        extra: dict):
    """One request through LiteLLM's Anthropic adapter, as upstream's proxy.

    Args:
        client: the AsyncOpenAI client, for Anthropic's address and key.
        model (str): LiteLLM's model id, `anthropic/<model>`.
        messages (list): the conversation so far.
        tools (list): the tool definitions, as the harness sends them.
        extra (dict): extra request parameters.

    Returns:
        The response, in Chat Completions form.
    """
    import litellm

    return await litellm.acompletion(model=model,
                                     api_base=str(client.base_url).rstrip("/"),
                                     api_key=client.api_key,
                                     messages=messages,
                                     tools=tools,
                                     timeout=client.timeout,
                                     **extra)


def responses_input(messages: list) -> list[dict]:
    """The conversation as Responses input, one item per message or call.

    Args:
        messages (list): Chat Completions messages.

    Returns:
        list[dict]: the same turns, in order.
    """
    items = []
    for message in messages:
        if message["role"] == "tool":
            items.append({
                "type": "function_call_output",
                "call_id": message["tool_call_id"],
                "output": responses_output(message["content"]),
            })
            continue
        if message.get("content"):
            items.append({
                "role": message["role"],
                "content": message["content"]
            })
        for call in message.get("tool_calls") or []:
            items.append({
                "type": "function_call",
                "call_id": call["id"],
                "name": call["function"]["name"],
                "arguments": call["function"]["arguments"],
            })
    return items


def responses_output(content: Any) -> Any:
    """A tool message's content, as a Responses function call's output.

    The harness passes an MCP result's content array through whole
    (`agent-eval.ts:262`), and upstream's proxy hands it to Chat Completions
    as an array of parts. The Responses spelling is an array too, part for
    part.

    Args:
        content (Any): the tool message's content.

    Returns:
        Any: the output, in the same parts.
    """
    if isinstance(content, str):
        return content
    return [{
        "type": "input_text",
        "text": part["text"]
    } if part["type"] == "text" else {
        "type": "input_image",
        "image_url": part["image_url"]["url"]
    } for part in content]


async def ask_openai(client, model: str, messages: list, tools: list,
                     extra: dict) -> ChatCompletion:
    """One request through the gateway's Responses endpoint.

    Args:
        client: the AsyncOpenAI client.
        model (str): the gateway's model id, `openai/<model>`.
        messages (list): the conversation so far.
        tools (list): the tool definitions, as the harness sends them.
        extra (dict): extra request parameters.

    Returns:
        ChatCompletion: the reply, in the form the harness reads.

    Raises:
        ValueError: for a request parameter with no Responses spelling here.
    """
    unread = set(extra) - RESPONSES_PARAMETERS
    if unread:
        raise ValueError(f"no Responses spelling for {sorted(unread)}")
    response = await client.responses.create(
        model=model,
        input=responses_input(messages),
        tools=[{
            "type": "function",
            **tool["function"]
        } for tool in tools],
        **({
            "reasoning": {
                "effort": extra["reasoning_effort"]
            }
        } if "reasoning_effort" in extra else {}))
    text = "".join(part.text for item in response.output
                   if item.type == "message" for part in item.content
                   if part.type == "output_text")
    calls = [
        ChatCompletionMessageToolCall(id=item.call_id,
                                      type="function",
                                      function=Function(
                                          name=item.name,
                                          arguments=item.arguments))
        for item in response.output if item.type == "function_call"
    ]
    # The reason Chat Completions would give. A cut-off reply without calls
    # still ends the draw, as upstream's loop ends on any reply without calls
    # (`agent-eval.ts:290`) and never reads the reason.
    cut = (response.incomplete_details.reason
           if response.status == "incomplete" else None)
    finish = CUT.get(cut) or ("tool_calls" if calls else "stop")
    counted = response.usage
    return ChatCompletion(
        id=response.id,
        object="chat.completion",
        created=int(response.created_at),
        model=response.model,
        choices=[
            Choice(index=0,
                   finish_reason=finish,
                   message=ChatCompletionMessage(role="assistant",
                                                 content=text or None,
                                                 tool_calls=calls or None))
        ],
        usage=CompletionUsage(
            prompt_tokens=counted.input_tokens,
            completion_tokens=counted.output_tokens,
            total_tokens=counted.total_tokens,
            prompt_tokens_details=PromptTokensDetails(cached_tokens=getattr(
                counted.input_tokens_details, "cached_tokens", None)),
            completion_tokens_details=CompletionTokensDetails(
                reasoning_tokens=getattr(counted.output_tokens_details,
                                         "reasoning_tokens", None))))
