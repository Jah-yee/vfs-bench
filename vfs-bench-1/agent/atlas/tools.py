import asyncio
import contextlib

from agents import function_tool
from atlas.constants import TOOL_CALL_TIMEOUT, TOOL_SERVER, TOOL_SERVER_PATH
from starlette.applications import Starlette
from starlette.routing import Route


def tool_server(functions: list) -> Starlette:
    """The mirage arm's tools as one MCP server, over streamable HTTP.

    What upstream's app is configured with on the mirage arm. It is the
    app's only server, so fastmcp connects to it directly and adds no prefix
    (`MCPConfigTransport`): the model sees `shell`. Each tool is advertised
    with the name, description and schema the agents SDK gives it, and
    called bare, so a raised error reaches the app the way any other
    server's does.

    A call still running when the harness stops waiting for it
    (`TOOL_CALL_TIMEOUT`) is cancelled then, which stops its command. The
    harness has told the model the call timed out and never aborts the
    request, so the command would otherwise run on and hold the shell's
    session, which runs one line at a time as bash does: the model's next
    command, however quick, would wait behind output nobody reads.

    An argument the schema does not declare is dropped, as the MCP arm's
    servers drop it: zod strips it in the TypeScript ones, and pydantic
    ignores it in the Python ones. The agents SDK's schema is strict
    (`additionalProperties: false`), so the MCP SDK's own check would refuse
    the whole call, and a `timeout` or `max_output_chars` beside a command
    would cost a request that the MCP arm would have answered. The
    schema is still what the model is shown, and still checked for the
    arguments it declares.

    Args:
        functions (list): the coroutines behind the arm's tools.

    Returns:
        Starlette: the server, at `TOOL_SERVER_PATH`.
    """
    import jsonschema
    from mcp import types
    from mcp.server.lowlevel import Server
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    tools = {}
    for function in functions:
        tool = function_tool(function)
        tools[tool.name] = (types.Tool(name=tool.name,
                                       description=tool.description,
                                       inputSchema=tool.params_json_schema),
                            function)
    server = Server(TOOL_SERVER)

    @server.list_tools()
    async def list_tools() -> list:
        return [tool for tool, _ in tools.values()]

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict) -> list:
        if name not in tools:
            raise ValueError(f"Unknown tool: {name}")
        tool, function = tools[name]
        declared = tool.inputSchema.get("properties", {})
        arguments = {k: v for k, v in arguments.items() if k in declared}
        try:
            jsonschema.validate(arguments, tool.inputSchema)
        except jsonschema.ValidationError as error:
            raise ValueError(
                f"Input validation error: {error.message}") from None
        try:
            text = await asyncio.wait_for(function(**arguments),
                                          TOOL_CALL_TIMEOUT)
        except TimeoutError:
            raise TimeoutError(f"stopped after {TOOL_CALL_TIMEOUT}s, when "
                               "the harness stopped waiting") from None
        return [types.TextContent(type="text", text=text)]

    manager = StreamableHTTPSessionManager(app=server)

    class Handler:
        """The session manager, as the ASGI app a route calls."""

        async def __call__(self, scope, receive, send):
            await manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    return Starlette(routes=[Route(TOOL_SERVER_PATH, endpoint=Handler())],
                     lifespan=lifespan)
