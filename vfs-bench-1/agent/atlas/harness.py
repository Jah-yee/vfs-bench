import asyncio
import contextlib
import os
import socket
import subprocess
from contextlib import AsyncExitStack
from pathlib import Path

import httpx
from atlas import outcome
from atlas.constants import (DEFAULT_MAX_TURNS, HARNESS_DIR, HARNESS_ENTRY,
                             HARNESS_ERROR, HARNESS_LOG, HARNESS_START, HEALTH,
                             IMAGE, KEEP_ALIVE, LLM_API_KEY, RUN_AGENT, SETUP,
                             TSX, WALL_CLOCK)
from atlas.proxy import ModelProxy
from atlas.relay import Relay
from atlas.serving import listen


def request(task_id: str, model: str, messages: list, enabled: list[str],
            extra: dict, max_turns: int) -> dict:
    """One task, as `run_eval.py` posts it (`run_one_task`).

    The task id, the model, the messages, the enabled tools, the image, a
    `task_id` tag, and, where set, `max_turns` and `extra_llm_params`.

    Args:
        task_id (str): upstream's id for the task.
        model (str): the model id.
        messages (list): the task, after a system message where the arm has
            one, as `run_eval.py --system-prompt` sends it.
        enabled (list[str]): the tools the harness keeps.
        extra (dict): `extra_llm_params`.
        max_turns (int): sent only where it is not the harness's default.

    Returns:
        dict: the request body.
    """
    body: dict = {
        "task_id": task_id,
        "model": model,
        "messages": messages,
        "enabledTools": enabled,
        "image": IMAGE,
        "tags": {
            "task_id": task_id
        },
    }
    if max_turns != DEFAULT_MAX_TURNS:
        body["max_turns"] = max_turns
    if extra:
        body["extra_llm_params"] = extra
    return body


async def start(model_url: str, sandbox_url: str, stack: AsyncExitStack,
                logs: Path) -> str:
    """Start upstream's harness, pointed at a model proxy and a sandbox.

    With no environment but what its `.env` would set: the two addresses,
    its port, and `LLM_API_KEY`. Every timeout keeps its default.

    Args:
        model_url (str): its `LLM_BASE_URL`.
        sandbox_url (str): its `MCP_SANDBOX_URL`.
        stack (AsyncExitStack): stops the harness.
        logs (Path): where its log goes, which is also its working
            directory, since it writes its own log there.

    Returns:
        str: its address.

    Raises:
        SystemExit: the harness is not installed.
        RuntimeError: it exited, or did not answer in time.
    """
    if not TSX.is_file():
        raise SystemExit(f"no harness installed at {HARNESS_DIR}; "
                         f"run `{SETUP}`")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    path = logs / HARNESS_LOG
    log = path.open("w")
    stack.callback(log.close)
    process = subprocess.Popen(
        ["node", str(TSX), str(HARNESS_ENTRY)],
        cwd=logs,
        env={
            "PATH": os.environ["PATH"],
            "HOME": os.environ["HOME"],
            "PORT": str(port),
            "LLM_BASE_URL": model_url,
            "LLM_API_KEY": LLM_API_KEY,
            "MCP_SANDBOX_URL": sandbox_url,
        },
        stdout=log,
        stderr=subprocess.STDOUT)
    stack.callback(process.wait)
    stack.callback(process.terminate)
    url = f"http://127.0.0.1:{port}"
    loop = asyncio.get_running_loop()
    deadline = loop.time() + HARNESS_START
    async with httpx.AsyncClient() as http:
        while loop.time() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"the harness exited ({process.returncode})"
                                   f"; see {path}")
            with contextlib.suppress(httpx.HTTPError):
                if (await http.get(f"{url}{HEALTH}")).is_success:
                    return url
            await asyncio.sleep(.1)
    raise RuntimeError(f"the harness did not answer in {HARNESS_START} s; "
                       f"see {path}")


async def run(client, model: str, messages: list, enabled: list[str],
              sandbox_url: str, *, task_id: str, extra: dict, max_turns: int,
              timeout: float, logs: Path) -> dict:
    """Drive one task through upstream's harness.

    The harness asks the model through a `ModelProxy` and reaches the app
    through a `Relay`, both served from this process. The run ends as
    `run_eval.py` ends it, after `timeout` seconds at most, and its answer
    is read the way `run_eval.py` reads it.

    Args:
        client: the AsyncOpenAI client, for the gateway.
        model (str): the model id.
        messages (list): the task, after a system message where the arm has
            one.
        enabled (list[str]): the tools the harness keeps.
        sandbox_url (str): the app.
        task_id (str): upstream's id for the task.
        extra (dict): `extra_llm_params`.
        max_turns (int): the turn limit.
        timeout (float): seconds the whole run may take.
        logs (Path): where the harness's log goes.

    Returns:
        dict: `status`, `final_output`, `usage`, `items` -- the messages sent
            and every message returned -- and `tool_calls`, how long each
            call took (`sandbox-client.ts:269` measures it and keeps it to
            itself).
    """
    body = request(task_id, model, messages, enabled, extra, max_turns)
    proxy, relay = ModelProxy(client), Relay(sandbox_url)
    async with AsyncExitStack() as stack:
        stack.push_async_callback(relay.close)
        model_url = await listen(proxy.app(), stack, KEEP_ALIVE)
        relayed = await listen(relay.app(), stack, KEEP_ALIVE)
        harness = await start(model_url, relayed, stack, logs)
        try:
            async with httpx.AsyncClient(timeout=None) as http:
                answer = await asyncio.wait_for(
                    http.post(f"{harness}{RUN_AGENT}", json=body), timeout)
        except TimeoutError:
            return outcome.drawn(WALL_CLOCK, f"{timeout}s", proxy.conversation
                                 or messages, proxy.usage, relay.calls)
        if not answer.is_success:
            return outcome.drawn(
                HARNESS_ERROR,
                f"HTTP {answer.status_code}: {answer.text[:300]}",
                proxy.conversation or messages, proxy.usage, relay.calls)
        outputs = answer.json()
    items = [*messages] + [
        output["data"] for output in outputs if output["type"] == "message"
    ]
    status, detail = outcome.status_of(outputs)
    return outcome.drawn(status, detail, items, proxy.usage, relay.calls)
