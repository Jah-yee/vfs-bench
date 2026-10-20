import asyncio
from contextlib import AsyncExitStack, ExitStack

import dataset
from atlas.constants import TOOL_SERVER, TOOL_SERVER_PATH
from atlas.serving import listen
from atlas.tools import tool_server


async def serve(arm: dict, task: str,
                stack: AsyncExitStack) -> tuple[str, list[str]]:
    """The app this arm's harness reaches, and the tools it enables.

    The MCP arm's app is up already, started by the arm, and enables the
    row's tools. The mirage arm's is started here, in the run's container,
    with one server: the arm's tools, served from this process.

    Args:
        arm (dict): what `build_arm` returned.
        task (str): the task name.
        stack (AsyncExitStack): stops whatever is started here.

    Returns:
        tuple[str, list[str]]: the app's address, and the tool names the
            request enables.
    """
    if arm.get("servers"):
        (app, ) = arm["servers"]
        return app.url, dataset.enabled_tools(task)
    address = await listen(tool_server(arm["functions"]), stack)
    closing = stack.enter_context(ExitStack())
    reached = await asyncio.to_thread(dataset.expose,
                                      f"{address}{TOOL_SERVER_PATH}", closing)
    url = await asyncio.to_thread(dataset.app, {TOOL_SERVER: {
        "url": reached
    }}, closing)
    return url, [function.__name__ for function in arm["functions"]]
