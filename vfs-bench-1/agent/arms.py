import dataclasses
import importlib
import os
import shutil
import sys
from contextlib import AsyncExitStack, contextmanager
from pathlib import Path

from agents import function_tool
from services import (MAX_TOOL_OUTPUT, REPO_ROOT, agent_workspace,
                      howtocook_corpus, logging_api, overlong_note,
                      web_fixture, yf_dsn)
from workspace import Workspace
from workspace import config_for as ts_config_for

sys.path.insert(0, str(REPO_ROOT / "server" / "mcp"))
sys.path.insert(0, str(REPO_ROOT / "task"))

import dataset  # noqa: E402
from mcp_servers import build_mcp_servers  # noqa: E402
from mcp_servers import model_tool_name  # noqa: E402
from mcp_servers import needed_local_tools  # noqa: E402
from mcp_servers import needed_mcp_servers  # noqa: E402

# Proxy settings that refuse every outbound connection while leaving the
# local fixtures -- the mock GWS server, the Notion fake, GreenMail and
# Postgres -- reachable. Port 9 is discard, which nothing listens on here,
# so a request fails at connect rather than hanging.
NO_NETWORK = {
    "http_proxy": "http://127.0.0.1:9",
    "https_proxy": "http://127.0.0.1:9",
    "HTTP_PROXY": "http://127.0.0.1:9",
    "HTTPS_PROXY": "http://127.0.0.1:9",
    "no_proxy": "localhost,127.0.0.1,::1",
    "NO_PROXY": "localhost,127.0.0.1,::1",
}

# The local tools that reach the network from inside this process, which
# is the one place NO_NETWORK does not already apply: this process keeps
# its own route out so it can call the model API. `ai_webpage_summary`
# fetches the page it summarises. `web_search` no longer calls Serper
# itself: its handler posts to the shared research transport on loopback,
# which searches live for both arms (server/seed/research.py).
AIRGAPPED_LOCAL_TOOLS = {"python_execute", "web_search", "ai_webpage_summary"}

_network_users = 0
_network_saved = {}


@contextmanager
def fixture_network():
    """Keep fixture proxies installed until the last overlapping tool exits.

    Entry and exit contain no await, so asyncio cannot interleave the count
    changes. The runner awaits the entire tool batch before its next model
    request. Restoration also runs on exceptions and cancellation.
    """
    global _network_users, _network_saved
    if _network_users == 0:
        _network_saved = {key: os.environ.get(key) for key in NO_NETWORK}
        os.environ.update(NO_NETWORK)
    _network_users += 1
    try:
        yield
    finally:
        _network_users -= 1
        if _network_users == 0:
            for key, value in _network_saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            _network_saved = {}


def upstream_image(task_dir: Path) -> bool:
    """Whether the MCP arm runs this task's model tools in upstream's image.

    Upstream runs every task's there; E2B tasks already run them in their
    sandbox. The other Kubernetes tasks reach their cluster through a
    tunnel on this host, which the container cannot, so they keep the
    confined host path.
    """
    from server.shared_workspace import active
    return (active() is None and dataset.NAME == "toolathlon"
            and "k8s" not in needed_mcp_servers(task_dir))


def public_network(task_dir: Path) -> bool:
    """Whether the MCP arm's model reaches the public network itself.

    Its terminal and `python_execute` have upstream's network in upstream's
    image, so the mirage arm's builtin HTTP has it there too. Elsewhere
    the model's own commands reach only the fixtures on either arm, but
    for the Kubernetes task with a browser: its sandbox keeps the network
    the browser needs, and both arms' native commands run there
    (server/shared_workspace.py `BROWSER_CAPTURES`).
    """
    servers = needed_mcp_servers(task_dir)
    shell = ("terminal" in servers
             or "python_execute" in needed_local_tools(task_dir))
    if "k8s" in servers:
        return (shell and dataset.NAME == "toolathlon"
                and "playwright_with_chunk" in servers)
    return upstream_image(task_dir) and shell


async def build_arm(args, task_dir: Path, stack: AsyncExitStack,
                    shell_log: list, run_context: dict) -> dict:
    """Build the one tool surface this run is measuring.

    Each arm gets the system prompt written for its own tools: the mirage
    arms get `VFS.md` and `SKILL.md`, which describe mounts and CLIs that
    do not exist on the other side, and the MCP arm gets upstream's own
    `agent_system_prompt.md`. Everything else about the run -- the model,
    the settings, the loop, the dump -- is identical, which is the point.

    Args:
        args: the parsed arguments.
        task_dir (Path): the task directory.
        stack (AsyncExitStack): owns whatever the arm has to close.
        shell_log (list): the mirage arms append every command to it.
        run_context (dict): Toolathlon's local tools read state out of it.

    Returns:
        dict: `name`, `instructions` and `tools`; on the MCP arm `servers`,
            and on the mirage arm `functions`, its tools unwrapped.
    """
    if args.tools in ("mcp", "gym"):
        workdir = build_workspace_dir(task_dir)
        open_services(task_dir, workdir, stack)
        from server.shared_workspace import active
        remote = active()
        # The model's Python, the terminal and the filesystem server run in
        # upstream's own task image where upstream_image says so.
        if upstream_image(task_dir):
            from server.execution import upstream_container
            stack.enter_context(upstream_container(workdir))
        visible_workdir = '/work' if remote else workdir
        # None where the dataset sends no system message at all, which is
        # Atlas: its harness passes the messages through untouched. The SDK
        # guards the system insert on truthiness, so "" and None both reach
        # the wire as no system message -- but the arm should say which it
        # means rather than rely on that.
        prompt_file = dataset.prompt(task_dir.name)
        instructions = None if prompt_file is None else rewrite_tool_names(
            prompt_file.read_text().replace(
                "!!<<<<||||workspace_dir||||>>>>!!", visible_workdir))
        if apply := getattr(dataset, "apply_system_prompt", None):
            instructions = apply(instructions, task_dir.name, visible_workdir)
        servers = build_mcp_servers(
            task_dir,
            workdir,
            sheets="gym" if args.tools == "gym" else "upstream")
        for server in servers:
            await stack.enter_async_context(server)
        run_context["_agent_workspace"] = workdir
        # local-python-execute shells out to `uv run --directory
        # <agent_workspace>`, and uv finds the project by walking up.
        # Upstream that lands on /workspace/pyproject.toml -- the synced
        # Toolathlon environment, with openpyxl, pandas, numpy, python-docx
        # and PyPDF2. Here the scratch dir sits under *this* repo, so it
        # walks up to ours instead and the interpreter comes up bare. Point
        # uv at the checkout so the arm gets the libraries the task was
        # written against.
        # Only where there are local tools to run: `local-python-execute` is
        # one of Toolathlon's, and a dataset without them has no checkout to
        # point uv at. Atlas reaches Python over MCP, on the venv its own
        # code-executor server spawns.
        # The same checkout `build_local_tools` imports them from, which is
        # what has the libraries they were written against -- and for
        # `toolathlon-gym` that is Toolathlon's, not its own.
        if getattr(dataset, "LOCAL_TOOLS", None):
            where = getattr(dataset, "tools_root", None) or dataset.root
            os.environ.setdefault("UV_PROJECT", str(where()))
        # The same redirect the mirage arm gets, for the same reason: this
        # arm reaches the Hub through `python_execute`, whose subprocess
        # inherits this environment, and `no_proxy` covers 127.0.0.1 so the
        # fake stays reachable while the airgap holds for everything else.
        # The token goes with it, because the bearer is the tenant and the
        # MCP server's bridge is the only thing that would otherwise carry
        # one -- leaving this arm's python reading somebody else's empty Hub.
        hub_redirect(task_dir)
        local_tools = build_local_tools(task_dir)
        counts = {
            server.name: len(await server.list_tools())
            for server in servers
        }
        counts["local"] = len(local_tools)
        print(f"mcp servers={len(servers)} tools={sum(counts.values())} "
              f"{counts}")
        return {
            "name": "toolathlon-mcp-agent",
            "instructions": instructions,
            "tools": local_tools,
            "servers": servers,
        }

    # The mirage arm, on mirage's TypeScript implementation: `pyodide` is
    # the only Python runtime with zlib, and 30 of the 46 workspaces mount
    # a wheel, which is a zip.
    workdir = mirage_env(task_dir)
    # Before the workspace is built, not after: a task's yaml interpolates
    # the address its CLIs are pointed at, and a service that starts second
    # would have its port read out of the environment before it had one.
    open_services(task_dir, workdir, stack)
    ts_ws = Workspace.create(ts_config_for(task_dir),
                             public_network=public_network(task_dir))
    stack.callback(ts_ws.close)
    shell = make_ts_shell(ts_ws, shell_log, task_dir.name)
    return {
        "name": "mirage-shell-agent",
        "instructions": build_shell_prompt(task_dir),
        "tools": [function_tool(shell)],
        # The same tools unwrapped, in the same order, for a harness that
        # serves them itself.
        "functions": [shell],
    }


def open_services(task_dir: Path, workdir: str, stack: AsyncExitStack) -> None:
    """Hold fixture services for both arms, after seeding and before setup.

    Args:
        task_dir (Path): the task directory.
        workdir (str): the run's workspace, already seeded.
        stack (AsyncExitStack): closes it when the run ends.
    """
    hold = getattr(dataset, "services", None)
    if hold is None:
        return
    stack.enter_context(hold(task_dir.name, workdir))


def resolve_task(args) -> Path:
    """The task directory one invocation means.

    `run_agent.py <dataset>/<task>` is the spelling, and it selects the
    dataset as well as the task. The bare `<task>` still works and means
    the default one, because 46 task READMEs publish their commands that
    way. `--task-dir` stays for the handful of callers that pass a path,
    and for a task whose directory is not named after it.

    Args:
        args: the parsed arguments.

    Returns:
        Path: the resolved task directory.

    Raises:
        SystemExit: neither was given, or the directory is not a task.
    """
    if args.task_dir:
        task_dir = (REPO_ROOT / args.task_dir).resolve()
    elif args.task:
        _, task = dataset.split(args.task)
        task_dir = dataset.local(task).resolve()
    else:
        raise SystemExit("usage: run_agent.py <dataset>/<task> "
                         "[--tools ...]; `ls task/*/` lists them")
    if not (task_dir / "shared" / "task.md").is_file():
        raise SystemExit(f"no task at {task_dir}: it has no "
                         f"shared/task.md")
    return task_dir


def build_workspace_dir(task_dir: Path) -> str:
    """Resolve and prepare the run's scratch directory on the host.

    The MCP arm always needs it: cli-mcp-server runs real commands. The
    mirage arm needs it only when the task ships an initial workspace, which
    a disk mount then serves; otherwise it mounts /work in RAM.

    A task's `initial_workspace/` is copied in, because both arms have to
    start from the fixture upstream gives them -- a task that says "follow
    the format of the example file in the workspace" is unanswerable
    without it, and forgetting the copy silently makes the run measure
    guessing instead of tool use. It is a clone where the volume can make
    one, which is the same tree for next to no space (`server.clone`). A
    script fixture may claim a source path under `workspace/`; that script
    owns the path's setup lifecycle, including consuming it, so the generic
    copy leaves it alone.

    Args:
        task_dir (Path): task directory.

    Returns:
        str: path to an existing scratch directory.
    """
    # Absolute, always: the MCP servers run with cwd set to this directory,
    # so a relative value resolves against the server's cwd rather than ours
    # and the whole arm dies with an opaque "Connection closed".
    agent_ws = str(agent_workspace(task_dir))
    os.environ["AGENT_WORKSPACE"] = agent_ws
    Path(agent_ws).mkdir(parents=True, exist_ok=True)
    fixture = dataset.initial_workspace(task_dir.name)
    seeded = {p.name for p in fixture.iterdir()} if fixture.is_dir() else set()
    leftovers = [
        p.name for p in Path(agent_ws).iterdir() if p.name not in seeded
    ]
    if leftovers:
        print(
            f"warning: scratch dir {agent_ws} is not empty "
            f"(possible leak into the run): {leftovers}",
            file=sys.stderr)
    managed_paths = {
        Path(*path.parts)
        for path in getattr(dataset, "managed_workspace_paths",
                            lambda _task: set())(task_dir.name)
    }

    def managed_in(directory, names):
        """Keep script-managed fixture paths out of a recursive copy."""
        relative = Path(directory).relative_to(fixture)
        return [
            name for name in names if Path(relative, name) in managed_paths
        ]

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from server.clone import clone
    for src in sorted(fixture.iterdir()) if fixture.is_dir() else []:
        if Path(src.name) in managed_paths:
            continue
        dst = Path(agent_ws) / src.name
        if dst.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dst, ignore=managed_in, copy_function=clone)
        else:
            clone(src, dst)
    prepare = getattr(dataset, "prepare_workspace", None)
    if prepare is not None:
        prepare(task_dir.name, Path(agent_ws))
    return agent_ws


def hub_redirect(task_dir: Path) -> None:
    """Point huggingface_hub at the Hub fake, for a task that has the Hub.

    `HF_ENDPOINT` and `HF_TOKEN` are huggingface_hub's own names, not this
    repo's choosing, so setting them points the MCP arm's own
    `python_execute` at the fake as well as the mirage arm's mount.

    The token is not decoration. The bearer IS the tenant on the Hub fake
    and a task's fixture is seeded under the task's name, so a client that
    sends none reads an empty Hub -- which comes back as 404 on every path
    rather than as an authentication error, and looks exactly like a
    repository that was never seeded.

    A task upstream does not give the Hub gets neither: its model's Python
    would otherwise find the task's name in `HF_TOKEN` and nothing else.

    Args:
        task_dir (Path): the task directory.
    """
    if "huggingface" in dataset.needed_mcp_servers(task_dir.name):
        os.environ.setdefault("HF_ENDPOINT", "http://127.0.0.1:5199")
        os.environ.setdefault("HF_TOKEN", task_dir.name)


def mirage_env(task_dir: Path) -> str:
    """Point a mirage arm's mounts and CLIs at this repo's fixtures.

    The task's yaml interpolates these, and the CLIs `cli/shims.mjs`
    spawns inherit them, so they have to be set before the workspace is
    built.
    Every one is a `setdefault`: an operator who has already exported an
    address means it.

    Shared by both mirage backends. They differ only in which mirage builds
    the workspace, so a variable set for one and not the other would be a
    difference between the arms that is not a difference in surface.

    Args:
        task_dir (Path): the task directory.

    Returns:
        str: the run's workspace, for whatever else has to be pointed at it.
    """
    os.environ.setdefault("GWS_URL", "http://127.0.0.1:19999")
    # The Drive folder a task's own seeder created, which the `gsheet` CLI's
    # `folderId` scope names and which a task's workspace.yaml interpolates.
    # Same default and same value as the MCP arm's DRIVE_FOLDER_ID, so no
    # surface is given a folder the others do not have. It lived in
    # `run_agent`, one copy each, which meant any third
    # caller of `build_workspace` got a hard failure on a missing variable
    # -- `tests/parity.py` was that third caller.
    os.environ.setdefault("DRIVE_FOLDER_ID", "f0001")
    os.environ.setdefault("NOTION_URL", "http://127.0.0.1:5091")
    os.environ.setdefault("GITHUB_URL", "http://127.0.0.1:19801")
    hub_redirect(task_dir)
    os.environ.setdefault("WHEELS_DIR", str(REPO_ROOT / "vendor" / "wheels"))
    os.environ.setdefault("PYODIDE_PACKAGES",
                          str(REPO_ROOT / "vendor" / "pyodide-packages"))
    os.environ.setdefault("TOOLATHLON_PYTHON",
                          str(REPO_ROOT / "vendor" / "toolathlon-python"))
    os.environ.setdefault("YF_DSN", yf_dsn())
    # Which corpus, from the seam where a dataset has an opinion. The two
    # that use this server do not ship the same one: Toolathlon resolves
    # `npx -y howtocook-mcp` and this repo pins npm's 0.2.2 behind it, while
    # GYM vendors 0.1.1 in its own tree. One recipe file per dataset, and
    # both arms of a draw read whichever it is.
    corpus = getattr(dataset, "howtocook_corpus", None) or howtocook_corpus
    os.environ.setdefault("HOWTOCOOK_CORPUS", str(corpus()))
    if "howtocook" in dataset.needed_mcp_servers(task_dir.name):
        if not Path(os.environ["HOWTOCOOK_CORPUS"]).is_file():
            raise RuntimeError(
                "The pinned recipe corpus is missing; run setup")
        if dataset.NAME == 'toolathlon':
            from services import howtocook_home
            if not (howtocook_home() / 'build/index.js').is_file():
                raise RuntimeError(
                    "The pinned recipe server is missing; run setup")
    # The two below are ASSIGNED where everything above is a `setdefault`,
    # and the difference is the difference between a global fact and a
    # per-task one. The pyodide packages, the yfinance DSN and the recipe
    # corpus are the same for every task in a process, so an operator who
    # exports one means it. These two carry the task's own name -- one in
    # the URL path, one in the fixture path -- so "already set" means "set
    # by a DIFFERENT task", and honouring it points this task at another
    # one's data.
    #
    # `run_agent` never noticed, because it runs one task per process.
    # `tests/parity.py` runs every task in one, and it took a second task
    # declaring the fetch server to show it: `dataset-license-issue` sorts
    # before `git-milestone`, set WEB_FIXTURE to its own empty capture, and
    # `git-milestone`'s four fetch cases then failed against a fixture that
    # was not theirs -- in the arm, not in the fixture, so the four names
    # that failed belonged to a task nothing had changed.
    #
    # Either arm's launch of the google-cloud server is handed this per-task
    # endpoint explicitly; whatever else reaches Cloud Logging inherits it.
    os.environ["CLOUD_LOGGING_API"] = logging_api(task_dir.name)
    # Only for the tasks that have one: the capture is a task's own
    # fixture, not a shared service.
    if (task_dir / "shared" / "web_fixture.json").is_file():
        os.environ["WEB_FIXTURE"] = str(web_fixture(task_dir))
    # A task whose fixture is a real tree (a git repository, a set of
    # documents) serves it from a disk mount, so ${AGENT_WORKSPACE} has to
    # resolve before the yaml is read.
    return build_workspace_dir(task_dir)


def build_shell_prompt(task_dir: Path) -> str:
    """Assemble the shell arm's system prompt from its two reference docs.

    vfs/VFS.md describes the filesystem, vfs/SKILL.md the CLIs.
    Neither names this
    task's data: the arms must discover ids the same way.

    Args:
        task_dir (Path): task directory holding vfs/.

    Returns:
        str: the assembled system prompt.
    """
    prompt = (
        "Your environment is described by two references, reproduced below: "
        "VFS.md (the filesystem) and SKILL.md (the command-line tools).\n\n"
        f"{(task_dir / 'vfs' / 'VFS.md').read_text()}\n"
        f"{(task_dir / 'vfs' / 'SKILL.md').read_text()}")
    if (dataset.NAME == 'toolathlon'
            and 'web_search' in dataset.needed_local_tools(task_dir.name)):
        prompt += (
            '\nUse `web-search web_search` with one JSON argument object; '
            '`web-search web_search --help` shows the original schema.\n')
    if apply := getattr(dataset, "apply_system_prompt", None):
        cwd_for = getattr(dataset, 'shell_cwd', None)
        cwd = (cwd_for(task_dir.name) if cwd_for else None) or '/work'
        prompt = apply(prompt, task_dir.name, cwd, shell=True)
    return prompt


def make_ts_shell_tool(ws, transcript: list, task: str):
    """Create the shell tool bound to a TypeScript-daemon workspace.

    Args:
        ws (Workspace): workspace commands execute in.
        transcript (list): mutable log of (command, output) pairs.
        task (str): task name for the dataset's output and cwd contract.

    Returns:
        The decorated function tool.
    """
    return function_tool(make_ts_shell(ws, transcript, task))


def make_ts_shell(ws, transcript: list, task: str):
    """The coroutine behind the shell tool, before the SDK wraps it.

    Separate from the tool because a harness that is not the SDK's calls
    it bare: the SDK's wrapper answers a raised error with text of its own,
    where Atlas's sandbox answers it with its own.

    Args:
        ws (Workspace): workspace commands execute in.
        transcript (list): mutable log of (command, output) pairs.
        task (str): task name for the dataset's output and cwd contract.

    Returns:
        Callable: `shell(command)`, returning the command's output.
    """

    cwd_for = getattr(dataset, "shell_cwd", None)
    cwd = cwd_for(task) if cwd_for else None
    format_output = getattr(dataset, "shell_output", None)
    # How a failed command says so, for a dataset whose upstream says it.
    exit_note = getattr(dataset, "shell_exit", None)
    # Toolathlon's cut and saved file, unless the dataset's upstream passes
    # results whole.
    capped = getattr(dataset, "TOOL_OUTPUT_CAP", MAX_TOOL_OUTPUT) is not None

    async def shell(command: str) -> str:
        """Run a shell command in the workspace and return its output.

        Args:
            command: the shell command line to execute.
        """
        result = await ws.execute_result_async(command, cwd=cwd)
        stdout, stderr = result.get("stdout", ""), result.get("stderr", "")
        out = f"{stdout}\n{stderr}" if stdout and stderr else stdout or stderr
        entry = {"command": command, "output": out}
        transcript.append(entry)
        if format_output is not None:
            out = format_output(task, command, stdout, stderr)
        if exit_note is not None and result.get("exit_code"):
            out = exit_note(out, result["exit_code"])
        if capped and len(out) > MAX_TOOL_OUTPUT:
            out = await ws.save_overflow(out)
        entry["model_output"] = out
        return out

    return shell


def rewrite_tool_names(prompt: str) -> str:
    """Rewrite a prompt's tool-name references to the names the model sees.

    The other half of the rename, and upstream does it in the same breath
    (`task_agent.py:505`): a prompt that tells the model to call
    `local-claim_done` names a tool that, after aliasing, does not exist.
    Every local tool is in the map rather than only this task's, which is
    upstream's `_flatten_local_tool_mappings`, plus the one legacy
    misspelling it hard-codes. MCP names are left alone, as upstream leaves
    them.

    Args:
        prompt (str): upstream's agent_system_prompt.md, workspace already
            interpolated.

    Returns:
        str: the same prompt with local tool names in their model spelling.
    """
    import re

    # A dataset with no local tools has no local tool names to rewrite. Atlas
    # is that: it has no in-process tool layer at all and reaches even Python
    # over MCP, so there is nothing here for it to rename -- and the map below
    # is built by importing Toolathlon's own modules out of Toolathlon's own
    # checkout, which such a dataset does not have to point `dataset.root()`
    # at in the first place.
    if not getattr(dataset, "LOCAL_TOOLS", None):
        return prompt

    # The checkout `LOCAL_TOOLS` names, which `build_local_tools` resolves
    # the same way and for the same reason.
    (getattr(dataset, "tools_root", None) or dataset.root)()
    aliases = {"local-claim-done": "local_claim_done"}
    for module, attribute in dataset.LOCAL_TOOLS.values():
        group = getattr(importlib.import_module(module), attribute)
        for tool in (group if isinstance(group, list) else [group]):
            aliases[tool.name] = model_tool_name(tool.name)
    # Longest first, so a name that is a prefix of another cannot claim it.
    for raw, shown in sorted(aliases.items(), key=lambda kv: -len(kv[0])):
        prompt = re.sub(
            rf"(?<![A-Za-z0-9_-]){re.escape(raw)}(?![A-Za-z0-9_-])", shown,
            prompt)
    return prompt


def build_local_tools(task_dir: Path) -> list:
    """Import the local tools the task's Toolathlon config asks for.

    Upstream's own mapping, name for name: `local_tool_mappings` in
    utils/roles/task_agent.py, which three of these names expand through
    rather than resolving to a single tool. `manage_context` is three tools
    and `history` five, so this task's five declared names are fourteen
    tools in front of the model, not five.

    Imported per declared name rather than all at once, which upstream can
    afford and this cannot: `web_search` needs bs4 and would otherwise be
    a hard import failure for the forty-four tasks that never ask for it.

    Args:
        task_dir (Path): task directory; its task_config.json is read.

    Returns:
        list: FunctionTool instances, in the order upstream builds them.
    """
    # Nothing declared, nothing to import -- and nothing to make the
    # dataset's checkout resolve for, which a dataset with no local-tool
    # layer does not have.
    declared = needed_local_tools(task_dir)
    if not declared:
        return []

    # Where the modules `LOCAL_TOOLS` names actually live, which is not
    # always the dataset's own checkout. `toolathlon-gym` runs Toolathlon's
    # local-tool layer over GYM's tasks, and both checkouts spell
    # `utils.aux_tools` -- so which one answers has to be decided here rather
    # than left to whichever landed on `sys.path` first.
    (getattr(dataset, "tools_root", None) or dataset.root)()
    tools = []
    for name in declared:
        module, attribute = dataset.LOCAL_TOOLS[name]
        group = getattr(importlib.import_module(module), attribute)
        for tool in (group if isinstance(group, list) else [group]):
            if name == 'web_search' and dataset.NAME == 'toolathlon':
                from server.seed.research import search_tool
                tool = dataclasses.replace(tool, on_invoke_tool=search_tool)
            if name == "python_execute" and dataset.NAME == "toolathlon":
                sys.path.insert(0, str(REPO_ROOT))
                from server.execution import (container, prepare_project,
                                              python_tool)
                from server.shared_workspace import active
                remote = active()
                if remote is None and container() is None:
                    prepare_project(dataset.root())
                tool = dataclasses.replace(tool,
                                           on_invoke_tool=remote.python_tool
                                           if remote else python_tool)
            if name in AIRGAPPED_LOCAL_TOOLS:
                from server.execution import container
                from server.shared_workspace import active

                # The remote Python environment owns its proxy settings;
                # the local E2B control connection must remain reachable.
                # In upstream's container the model's Python has upstream's
                # network, as it does there.
                if name != 'python_execute' or (active() is None
                                                and container() is None):
                    tool = airgapped_tool(tool)
            # Toolathlon's function-result hook covers every local tool,
            # including the overlong-output readers themselves.
            if (dataset.NAME == "toolathlon"
                    or name != "handle_overlong_tool_outputs"):
                tool = truncating_tool(tool)
            tools.append(
                dataclasses.replace(tool, name=model_tool_name(tool.name)))
    return tools


def airgapped_tool(tool):
    """Run a local tool with the network closed, fixtures still reachable.

    `python_execute` writes the model's code to a file and runs it under
    `uv run`, which inherits this process's environment, so the code has the
    host's network. That is the second door out of the fixture after the
    terminal server's `curl` (see NO_NETWORK), and the more important one,
    because it takes arbitrary code rather than an allowlisted command.

    The environment is set around the call rather than for the process,
    because this process also talks to the model API and must keep its own
    route out. Overlapping calls share one environment scope, restored only
    when the last tool finishes, before the runner's next model request.

    Args:
        tool: a FunctionTool.

    Returns:
        The same tool with its invoke wrapped.
    """
    import dataclasses

    inner = tool.on_invoke_tool

    async def airgapped(context, params):
        """Invoke the tool with NO_NETWORK in the environment."""
        with fixture_network():
            return await inner(context, params)

    return dataclasses.replace(tool, on_invoke_tool=airgapped)


def truncating_tool(tool):
    """Cap a local function tool's result the way Toolathlon caps it.

    Upstream applies MAX_SINGLE_TURN_RETURN_CHARS to function-tool results in
    custom_run_impl.py, not just to MCP results. That patch monkey-patches a
    call path openai-agents 0.18 no longer has, so without this wrapper the
    local tools -- `local-python-execute` above all -- are the one uncapped
    path in either arm, and a single cell dump rides in the context for the
    rest of the run.

    Toolathlon applies this to the overlong-output readers as well.

    Args:
        tool: a FunctionTool.

    Returns:
        The same tool with its invoke wrapped.
    """
    import dataclasses

    inner = tool.on_invoke_tool

    async def capped(context, params):
        out = await inner(context, params)
        text = out if isinstance(out, str) else str(out)
        if len(text) <= MAX_TOOL_OUTPUT:
            return out
        workdir = None
        try:
            workdir = context.context.get("_agent_workspace")
        except AttributeError:
            pass
        return overlong_note(text, workdir or os.environ["AGENT_WORKSPACE"])

    return dataclasses.replace(tool, on_invoke_tool=capped)
