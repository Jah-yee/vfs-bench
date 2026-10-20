import asyncio
import errno
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import ExitStack, contextmanager
from functools import cache
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]

NAME = "mcpatlas"

# Where this repo keeps a task. There is no second half to point at: MCP-Atlas
# ships its 500 tasks as a HuggingFace dataset, not as a directory tree, so
# the row a task was cut from is committed beside the fixture, in
# `shared/atlas.json`, rather than read out of a checkout. That is the whole
# structural difference from `toolathlon`, and it is why the seam below has no
# `root()`, no `POOL` and no `evaluator_argv`.
LOCAL = ("task", NAME)
MANIFEST = ("task.json", )
SEEDER = ("task", NAME, "script", "seed_task.py")

# The dataset row, as `script/derive_task.py` writes it out of the pinned
# revision: the upstream TASK id, its ENABLED_TOOLS, and the GTFA_CLAIMS the
# answer is graded on. Every field is upstream's, which is what lets the whole
# file be derived and `dvc status` catch it drifting.
DECLARATION = ("shared", "atlas.json")

# Both arms start from the same tree, and there is exactly one of it. Atlas
# bakes a single `/data` into a single sandbox image that all 500 tasks share
# -- the CSVs its Dockerfile moves there, the repositories it clones into
# `repos/`, and the code executor's venv it `uv sync`s -- so a fixture
# committed per task would be modelling the upstream wrong. The MCP arm's
# servers read the image's own `/data` in the run's container, and the mirage
# arm mounts a copy of the same directory taken out of the same image. Same
# bytes, and the same path on both.
SUBMODULE = ("submodule", "mcp-atlas")

# How much of a tool result the model is shown: upstream's `tool_output_cap`,
# which its harness applies only when a run sets it (`agent-eval.ts:260`) and
# `run_eval.py:360` leaves unset, "uncapped". So the mirage arm's shell answers
# whole, as the harness passes the MCP arm's results whole, with none of
# Toolathlon's cut, note or saved file.
TOOL_OUTPUT_CAP = None

# Why `whole_mount.py`, which each task's workspace.yaml runs every command
# under, refused a command, by the command it refused: it refuses `cat` only
# for a whole Airtable table, MongoDB collection or Notion `rows.jsonl`,
# `notion` only for asking for everything, and anything else only for walking
# a whole mount or reading every table of a base at once.
REFUSED_TABLE = ("a whole table; read the records you need rather than all "
                 "of them")
REFUSED_NOTION = ("everything at once; give a search a `query` or `filter`, "
                  "and a database query a `filter` or `filter_properties`")
REFUSED_MOUNT = ("point it at the directory or file you need rather than at a "
                 "whole mount")
REFUSED = {"cat": REFUSED_TABLE, "notion": REFUSED_NOTION}


def shell_output(task: str, command: str, stdout: str, stderr: str) -> str:
    """A mirage-arm command's output, with why the arm refused it, if it did.

    Mirage refuses a command `whole_mount.py` denies in bash's own voice,
    `<command>: Permission denied`, and keeps the reason on the result's
    record. Its own agent adapters print that reason as one more line,
    `policy denied: <reason>`, and this prints the same line for each such
    refusal. A line refused whole says so on stderr; a command refused where
    it stands says so where its stderr goes, so `2>&1` puts it on stdout.
    Every other command answers as the shell joins it.

    Args:
        task (str): the task name.
        command (str): the command line the model sent.
        stdout (str): its standard output.
        stderr (str): its standard error.

    Returns:
        str: stdout and stderr, and a line for each refusal.
    """
    output = f"{stdout}\n{stderr}" if stdout and stderr else stdout or stderr
    for refused in re.findall(r"^([\w.-]+): Permission denied$",
                              f"{stdout}\n{stderr}", re.MULTILINE):
        reason = REFUSED.get(refused, REFUSED_MOUNT)
        output = output.removesuffix("\n") + f"\npolicy denied: {reason}"
    return output


def shell_exit(output: str, code: int) -> str:
    """Say that a mirage-arm command failed, in upstream's own words.

    The words are the line `cli-mcp-server==0.2.5`, the shell server Atlas
    pins, ends every `run_command` reply with. It is added only when the
    command exited non-zero, so a successful command answers as it did. A
    failure that printed nothing -- a `grep` with no match, a `curl -s` with no
    network -- otherwise reached the model as the harness's `success`
    (`sandbox-client.ts:263`), which a failing command never says.

    Args:
        output (str): the command's stdout and stderr, as the shell sends them.
        code (int): the command's non-zero exit status.

    Returns:
        str: the output with the status line after it.
    """
    return f"{output}\nCommand completed with return code: {code}"


def workspace_config(body: dict) -> None:
    """Take Mirage's own line caps off the mirage arm's commands.

    Mirage cuts `cat`, `grep`, `rg`, `head` and `tail` at 2,000 lines by
    default and says so in a note, where upstream's harness passes every tool
    result whole (`TOOL_OUTPUT_CAP`). The workspace-level entry covers a
    command on any mount and one reading a pipe, which a mount's entry does
    not reach; each entry replaces the whole limit, so the deadline is
    restated.

    Args:
        body (dict): the task's workspace yaml, as loaded.
    """
    from mirage.policy.builtin.output_cap import DEFAULT_COMMAND_LIMITS

    limits = body.setdefault("command_limits", {})
    for command, default in DEFAULT_COMMAND_LIMITS.items():
        limits.setdefault(command,
                          {"timeout_seconds": default.timeout_seconds})


# Atlas grades the agent's final message against the row's claims rather
# than reading a fixture back out of a fake, so `grading.grade` hands this
# dataset's grader the run's dump. Toolathlon's grader never sees one.
GRADES_TRANSCRIPT = True

# No stack to bring up. This dataset's fixture is one image: `services`
# starts a container of it per run, the mirage arm mounts a copy of its
# `/data` taken into a per-run workspace, and the services some tasks read
# -- Notion, Slack and Calendar, mirage's fakes, and MongoDB -- are started
# per run too, so no service holds a previous arm's state and there is
# nothing for `stack.up()` to do.
NEEDS_STACK = False

# What a dump records of how Atlas asks. `parallel_tool_calls` is None
# because Atlas never sends the field: its request is `{model, messages,
# tools}` and nothing else (`litellm-strategy.ts:51`), so the provider
# default stands. The turn limit is the harness's own default, which a
# request leaves alone unless `--max-turns` says otherwise.
PARALLEL_TOOL_CALLS = None
MAX_TURNS = 256

# Atlas has no agent framework at all. Its harness is a TypeScript service,
# `services/agent-harness`: a hand-written `for` loop that asks the model
# over Chat Completions and reaches every tool through one HTTP app,
# `services/agent-environment`. Both are run here as they are, rather than
# reproduced (`agent/atlas/`), and both arms of a draw run on them
# -- the surface is the only thing allowed to differ.
LOOP = "atlas"

# Where the MCP arm's servers run: upstream's own sandbox image, one
# container per run, which `services` starts and `server/mcp/setup_mcpatlas.py`
# builds -- the image itself, and the four servers it fetches from a GitHub
# branch installed at a commit. Every server is started as upstream's app
# starts it, so each sees what it sees there -- `/data`, `/root`, the tree
# the image installed -- and no path, home or machine of this repo's reaches
# the model through it.
SETUP = "uv run python server/mcp/setup_mcpatlas.py"
IMAGE = ("ghcr.io/scaleapi/mcp-atlas@sha256:"
         "24e6ed3534916afe2c6825382da159a30e23516ef612be5d074fd96a74f9184c")

# The environment upstream's app starts a server in, read off a live one's
# `/proc/<pid>/environ` inside the image: fastmcp's stdio transport hands
# each the MCP SDK's default environment of the app's own process -- $HOME,
# and a $PATH `uv run` put the app's venv at the front of -- plus the
# template's `env`, in the app's working directory. Nothing else of the
# container's own environment reaches a server.
HOME = "/root"
PATH = ("/agent-environment/.venv/bin:/usr/local/bin:/usr/local/sbin:"
        "/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
WORKDIR = "/agent-environment"

# Upstream's server config, which its entrypoint `envsubst`s into the one the
# app reads. From the pinned checkout; the image carries the same file, byte
# for byte.
TEMPLATE = ("services/agent-environment/src/agent_environment/"
            "mcp_server_template.json")

# The four servers whose template line fetches a GitHub branch -- `npx -y
# https://github.com/...` and `uvx --from git+...`, no version at all --
# started from the commits `docker/mcpatlas.Dockerfile` installs instead.
PINNED = {
    "github":
    ("node",
     "/opt/vfs-bench/github/node_modules/@smithery/mcp-github/dist/cli.js"),
    "weather":
    ("node",
     "/opt/vfs-bench/weather/node_modules/@smithery/weather/bin/weather.js"),
    "weather-data":
    ("/opt/vfs-bench/weather-data/.venv/bin/weather-mcp-server", ),
    "pubmed":
    ("/opt/vfs-bench/pubmed/.venv/bin/python", "-m", "pubmed_server"),
}

# Where `services` copies `redirect/github/github_hook.mjs` into the run's
# container, for the GitHub server's `node --import`.
GITHUB_HOOK = "/opt/vfs-bench/github_hook.mjs"

# The GitHub tasks that read live GitHub, as upstream's do, rather than the
# fake: every one whose row asks about something on GitHub. The fake holds
# nothing, so it answers the others' searches as GitHub would a search for
# what it does not hold, and it could not hold these faithfully: they ask
# about repositories with merges in their history, and the fake keeps one
# parent a commit, so what a merge brought in is missing from its lists.
GITHUB_LIVE = frozenset({
    "serpent-repo-first-pr-branch", "snake-repo-commit-count",
    "storyteller-creator-first-commit", "storyteller-last-commit"
})


def at_pin(path: str) -> subprocess.CompletedProcess:
    """One file of the pinned checkout, as `pinned`'s commit has it.

    Args:
        path (str): the path inside the checkout.

    Returns:
        subprocess.CompletedProcess: `git show`'s run, its text as stdout.
    """
    return subprocess.run([
        "git", "-C",
        str(REPO_ROOT.joinpath(*SUBMODULE)), "show", f"{pinned()}:{path}"
    ],
                          capture_output=True,
                          text=True,
                          check=False)


@cache
def template() -> dict:
    """Upstream's servers as its template names them, before `envsubst`.

    Returns:
        dict: `mcpServers`, keyed by server.

    Raises:
        SystemExit: the pinned checkout has no template.
    """
    shown = at_pin(TEMPLATE)
    if shown.returncode != 0:
        raise SystemExit(f"{NAME}: no {TEMPLATE} at {pinned()[:12]}: "
                         f"{shown.stderr.strip()}")
    return json.loads(shown.stdout)["mcpServers"]


def container() -> str:
    """The run's container, which `services` starts.

    Returns:
        str: its name.

    Raises:
        SystemExit: no container is up.
    """
    name = os.environ.get("MCPATLAS_CONTAINER", "")
    if not name:
        raise SystemExit(f"{NAME}: no container is up; its servers start "
                         f"inside `services`")
    return name


def inside(command: str,
           *args: str,
           env: dict | None = None,
           cwd: str | None = None) -> dict:
    """A launch of `command` in the run's container, as upstream's app does.

    `env -i`, so the server is given upstream's environment and no more; the
    values travel in the docker client's own environment, by name, so no key
    is ever on a command line.

    Args:
        command (str): what to run.
        *args (str): its arguments.
        env (dict | None): the variables the template sets.
        cwd (str | None): the run's workspace, which the docker client runs
            in and a tool-command transport reads as its caller's.

    Returns:
        dict: what `MCPServerStdio` is constructed from.
    """
    env = env or {}
    script = " ".join([
        "exec env -i", f"HOME={HOME}", f"PATH={PATH}",
        *(f'{name}="${name}"' for name in env), '"$@"'
    ])
    return {
        "command":
        "docker",
        "args": [
            "exec", "--interactive", "--workdir", WORKDIR,
            *(flag for name in env for flag in ("--env", name)),
            container(), "sh", "-c", script, "sh", command, *args
        ],
        "env":
        env,
        "cwd":
        cwd,
    }


def spec(name: str) -> dict:
    """One server, from its template line, with the keys `envsubst` fills.

    `uvx pkg==ver` resolves a fresh environment from PyPI on every start,
    inside the image as anywhere, although the image's own `uv tool install`
    of the same pin is on $PATH -- so that executable runs instead, which is
    the tree the image froze; `uvx --from pkg==ver exe` runs `exe` the same
    way. An `npx pkg@ver` runs as written: npm finds the image's global
    install and fetches nothing.

    Args:
        name (str): the server, as the template keys it.

    Returns:
        dict: its entry in the app's config: `command`, `args`, and `env`
            where it has one, as the template writes them, with the
            variables `added` declares for it.
    """
    extra = added(name)
    server = template()[name]

    def filled(value: str) -> str:
        return re.sub(r"\$\{([^}]+)\}", lambda found: key(found[1], name),
                      value)

    command, *args = PINNED.get(name) or (server["command"],
                                          *server.get("args", []))
    if command == "uvx" and args[0] == "--from":
        command, args = args[2], args[3:]
    elif command == "uvx":
        command, args = args[0].split("==", 1)[0], args[1:]
    args = [filled(arg) for arg in args]
    env = {
        variable: filled(value)
        for variable, value in (server.get("env") or {}).items()
    }
    env.update(extra)
    return {
        "command": command,
        "args": list(args),
        **({
            "env": env
        } if env else {})
    }


def launch(name: str, workdir: str) -> dict:
    """One server started by hand in the run's container, as the app would.

    For what reaches a server with no app in between: the mirage arm's
    tool-command CLIs, and the parity tests.

    Args:
        name (str): the server, as the template keys it.
        workdir (str): the run's workspace.

    Returns:
        dict: what `MCPServerStdio` is constructed from.
    """
    entry = spec(name)
    return inside(entry["command"],
                  *entry["args"],
                  env=entry.get("env"),
                  cwd=workdir)


def reach(url: str) -> str:
    """The address the container reaches a service of this machine's at.

    Args:
        url (str): the service, as this machine reaches it.

    Returns:
        str: the same service from inside the container, at the host
            `services` chose for it.
    """
    parts = urlsplit(url)
    return parts._replace(
        netloc=f"{os.environ['MCPATLAS_HOST']}:{parts.port}").geturl()


def bridge(name: str) -> str:
    """This machine's own address on the container's network, if it has one.

    A Linux engine's gateway is an address of this machine's, which a relay
    can listen on. Docker Desktop's is inside its VM, and there the VM hands
    `host.docker.internal` to this machine's loopback itself.

    Args:
        name (str): the container.

    Returns:
        str: the gateway, or "" where it is not this machine's.
    """
    gateway = subprocess.run([
        "docker", "inspect", "--format",
        "{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}", name
    ],
                             capture_output=True,
                             text=True,
                             check=True).stdout.strip()
    try:
        socket.create_server((gateway, 0)).close()
    except OSError as error:
        if error.errno != errno.EADDRNOTAVAIL:
            raise
        return ""
    return gateway


def relay(address: str, port: int, stack: ExitStack) -> None:
    """Hand every connection to `address:port` to the loopback's `port`.

    Args:
        address (str): an address of this machine's the container reaches.
        port (int): the service's port, on both.
        stack (ExitStack): stops the relay when the run ends.
    """
    import socketserver
    import threading

    def copy(source, sink) -> None:
        """One direction, until its sender is done."""
        try:
            while data := source.recv(65536):
                sink.sendall(data)
        except OSError:
            pass
        finally:
            try:
                sink.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    class Pipe(socketserver.BaseRequestHandler):
        """One connection, to the service and back."""

        def handle(self):
            with socket.create_connection(("127.0.0.1", port)) as there:
                back = threading.Thread(target=copy,
                                        args=(there, self.request),
                                        daemon=True)
                back.start()
                copy(self.request, there)
                back.join()

    server = socketserver.ThreadingTCPServer((address, port), Pipe)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    stack.callback(server.server_close)
    stack.callback(server.shutdown)


def server(name: str):
    """A builder for a server started as its template line says.

    With the variables `added` declares for it, through `spec`.

    Args:
        name (str): the server.

    Returns:
        Callable: the builder.
    """

    def build(at) -> dict:
        """Its template line, in the run's container."""
        return launch(name, at.workdir)

    return build


def desktop_commander(at) -> dict:
    """desktop-commander, handed over the way upstream's sandbox hands it.

    Its config is a file in $HOME that the server writes on first start,
    and upstream's app then makes one call on it -- `set_config_value` --
    in a session of its own (`agent_environment/main.py:97`). Both leave
    traces the model can read: `get_config` is one of the tools Atlas
    enables, and what it answers counts that call and that session
    (`toolCounts.set_config_value: 1`, `totalSessions: 2` in the dataset's
    own trajectory). So the call is made rather than its result written, from
    an empty config every launch, and the arm's own session is its second.

    Args:
        at: the `Launch` the builder is given.

    Returns:
        dict: what `MCPServerStdio` is constructed from.
    """
    params = launch("desktop-commander", at.workdir)
    subprocess.run([
        "docker", "exec",
        container(), "rm", "-rf", f"{HOME}/.claude-server-commander"
    ],
                   check=True)
    start(params, "set_config_value", {
        "key": "allowedDirectories",
        "value": ["/data"]
    })
    return params


def start(params: dict, tool: str, arguments: dict) -> None:
    """Bring a server up, make one call in a session of its own, and stop.

    On a thread with its own loop, so it works whether or not the caller is
    already inside one.

    Args:
        params (dict): the server's launch.
        tool (str): the tool to call.
        arguments (dict): its arguments.

    Raises:
        RuntimeError: the call answered with an error.
    """
    from concurrent.futures import ThreadPoolExecutor

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def call():
        child = StdioServerParameters(**params)
        # Its banner is not the run's; an error is in the call's result.
        with open(os.devnull, "w") as quiet:
            async with stdio_client(child, errlog=quiet) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(tool, arguments)

    with ThreadPoolExecutor(1) as pool:
        result = pool.submit(asyncio.run, call()).result()
    if result.isError:
        raise RuntimeError(f"{NAME}: {tool} failed at start: "
                           f"{result.model_dump_json()}")


def key(name: str, server: str) -> str:
    """One of the keys a server reads, from this run's environment.

    A server whose key is missing is dropped upstream rather than failed
    (`mcp_client.py:62`), leaving the task to run without it; here that
    would be a draw measuring a surface Atlas never meant, so it stops.

    Args:
        name (str): the variable.
        server (str): the server that reads it, for the message.

    Returns:
        str: the value.

    Raises:
        SystemExit: it is not set.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{NAME}: the {server} server needs {name}; "
                         f"see .env.example")
    return value


def added(name: str) -> dict:
    """The variables this repo adds to one server's environment.

    Each is a divergence from upstream's template, declared above the branch
    that adds it; a server with no branch is given none.

    Args:
        name (str): the server.

    Returns:
        dict: variable to value.
    """
    # Notion's own server, against mirage's Notion fake. Upstream's server
    # reads a live workspace imported from Atlas's export; this one reads the
    # fake, seeded from the same export by `server/seed/atlas_exports.py`,
    # through the base URL the server itself takes.
    #
    # Divergences: `BASE_URL`, and `NOTION_TOKEN`, which `services` sets to
    # the fake's tenant where upstream's names an integration. The header is
    # upstream's otherwise, `Notion-Version` included.
    if name == "notion":
        return {"BASE_URL": reach(os.environ["NOTION_URL"])}
    # slack-mcp-server, on a session token, against mirage's Slack fake.
    # Upstream's server reads a live workspace imported from Atlas's export,
    # on the `xoxc`/`xoxd` pair its template names; this one reads the fake,
    # seeded from the same export, through `server/fakes/slack_host.py` --
    # the server takes no base URL, only a proxy and a CA of its own.
    #
    # Divergences: the proxy and the CA; the tokens, which `services` sets to
    # the fake's tenant; and `auth.test`, which names the fake's own member
    # and team. `conversations_add_message` refuses, as upstream's does,
    # because the template sets no `SLACK_MCP_ADD_MESSAGE_TOOL`.
    if name == "slack":
        return {
            variable: os.environ[variable]
            for variable in ("SLACK_MCP_PROXY", "SLACK_MCP_SERVER_CA")
        }
    # @geobio/google-workspace-server, against mirage's Google Workspace
    # fake. Upstream's server reads a live account Atlas's `.ics` was
    # imported into; this one reads the fake, seeded from the same export by
    # `server/seed/atlas_exports.py`, through `server/fakes/slack_host.py` --
    # its googleapis client sends to oauth2.googleapis.com and
    # www.googleapis.com and takes no base URL, but gaxios tunnels through
    # `HTTPS_PROXY` and Node trusts `NODE_EXTRA_CA_CERTS`. `npx` reads the
    # same proxy for its registry lookup at every start, so `NO_PROXY` sends
    # that where upstream's goes.
    #
    # Divergences: the proxy, the CA and the registry's exemption from it;
    # and the three OAuth values, which `services` sets to placeholders the
    # fake takes, where upstream's name a live client -- so a request that
    # missed the proxy would be refused by Google rather than read an
    # account.
    if name == "google-workspace":
        return {
            "HTTPS_PROXY": os.environ["GOOGLE_WORKSPACE_PROXY"],
            "NO_PROXY": "registry.npmjs.org",
            "NODE_EXTRA_CA_CERTS": os.environ["GOOGLE_WORKSPACE_CA"],
        }
    # @felores/airtable-mcp-server, against mirage's Airtable fake.
    # Upstream's server reads a live base a user copies from Atlas's share
    # link; this one reads the fake, seeded with the same base as mirage
    # captured it from that link, through `server/fakes/slack_host.py` -- the
    # server sends everything to `https://api.airtable.com/v0` and takes no
    # base URL, but its axios tunnels through `HTTPS_PROXY` and Node trusts
    # `NODE_EXTRA_CA_CERTS`. `npx` reads the same proxy for its registry
    # lookup at every start, so `NO_PROXY` sends that where upstream's goes.
    #
    # Divergences: the proxy, the CA and the registry's exemption from it;
    # and `AIRTABLE_API_KEY`, which `services` sets to the token the
    # fixture's account answers to, where upstream's names a personal access
    # token.
    if name == "airtable":
        return {
            "HTTPS_PROXY": os.environ["AIRTABLE_PROXY"],
            "NO_PROXY": "registry.npmjs.org",
            "NODE_EXTRA_CA_CERTS": os.environ["AIRTABLE_CA"],
        }
    # @smithery/mcp-github, against mirage's GitHub fake. Upstream's server
    # reads live GitHub on a personal token, which reaches whatever that
    # token can -- private repositories included. This one reads the fake,
    # which holds nothing, for the tasks whose rows ask about nothing on
    # GitHub. The server sends everything to `https://api.github.com`
    # through Octokit and takes no base URL, and Node 20's `fetch` honours no
    # proxy, so `redirect/github/github_hook.mjs` moves the origin inside
    # `fetch`.
    #
    # Divergences: the hook and the origin it is given; and `GITHUB_TOKEN`,
    # which `services` sets to the fake's tenant, where upstream's names a
    # personal token. The tasks in `GITHUB_LIVE` start it as written, on
    # live GitHub, and `services` sets none of this for them.
    if name == "github" and "GITHUB_API_URL" in os.environ:
        return {
            "NODE_OPTIONS": f"--import={GITHUB_HOOK}",
            "GITHUB_API_URL": os.environ["GITHUB_API_URL"],
        }
    # wikipedia-mcp, logged in to Wikimedia with a token of this repo's.
    # Wikimedia limits the API requests of a client that is not logged in by
    # its User-Agent, 200 a minute (mediawiki.org,
    # Wikimedia_APIs/Rate_limits), and every copy of this server sends the
    # same one, so everyone who runs it shares that budget and is answered
    # 429 when it is spent -- which the server's search reports as
    # `no_results`, even for a title with an article. The server takes a
    # personal access token for this, and sends it on its searches and
    # coordinate lookups, which then count against the token's own budget.
    #
    # Divergences: `WIKIPEDIA_ACCESS_TOKEN`, which upstream's template does
    # not set. The server's article reads (`get_article`, `get_summary` and
    # the tools built on them) go through wikipediaapi, which it never hands
    # the token, so they share the User-Agent's budget as upstream's do.
    if name == "wikipedia":
        return {
            "WIKIPEDIA_ACCESS_TOKEN": key("WIKIPEDIA_ACCESS_TOKEN",
                                          "wikipedia")
        }
    return {}


# The servers started as their template line says, less what `spec` changes
# of every one, and desktop-commander, started as upstream's app starts it.
#
# Every divergence of this arm's from upstream's is declared here, beside
# the registry `mcp_servers.server_params` reads in place of its own:
#
# - `PINNED`'s four run at the commit each branch held when the image was
#   built, where upstream's `npx -y` and `uvx --from git+` run whatever the
#   branch holds at each start.
# - A `uvx pkg==ver` runs the image's own install of that pin, where
#   upstream's resolves a fresh environment from PyPI at each start.
# - fetch's readabilipy is installed from a lock when the image is built,
#   where upstream's installs it on the first page each sandbox fetches.
# - notion, slack, google-workspace, airtable and github read mirage's fakes,
#   and wikipedia is logged in to Wikimedia with a token upstream's template
#   does not set, as `added` declares.
# - mongodb reads a MongoDB of the run's. Upstream's server reads the user's
#   own Atlas cluster, which `data_exports/README.md` restores Atlas's
#   `video_game_store` dump into; this one reads a MongoDB started for the
#   run and restored from the same dump by `server/seed/atlas_exports.py`,
#   on the connection string the template reads. It is MongoDB 7.0 where an
#   Atlas cluster runs 8.0, for the reason `atlas_exports.MONGO_IMAGE`
#   gives; a standalone server rather than an Atlas replica set, so
#   `list-databases` names `config` beside `admin` and `local`; and every
#   size it reports is this server's own.
# - The app's config is written whole, from these entries, where upstream's
#   entrypoint `envsubst`s the template into it; and the app runs the
#   task's servers, where upstream's runs every server it has keys for. The
#   harness advertises only the row's tools either way, but a tool the model
#   names that the row leaves out still runs upstream if its server is up,
#   and here fails as unknown.
# - The app is the image's, on the image's venv: its code is the pinned
#   checkout's byte for byte, but its `uv.lock` predates the checkout's
#   starlette bump.
#
# Keyed by the name Atlas gives each server in its own
# `mcp_server_template.json`, because that key is what prefixes every tool
# name the model sees. `mcp_servers.server_params` reads this dict in
# preference to its own, so a second benchmark is a seam rather than an edit.
SERVERS = {
    **{
        name: server(name)
        for name in (
            "filesystem",
            "mcp-code-executor",
            "memory",
            "weather",
            "git",
            "fetch",
            "e2b-server",
            "met-museum",
            "national-parks",
            "clinicaltrialsgov-mcp-server",
            "whois",
            "context7",
            "oxylabs",
            "arxiv",
            "cli-mcp-server",
            "weather-data",
            "pubmed",
            "exa",
            "open-library",
            "calculator",
            "google-maps",
            "osm-mcp-server",
            "ddg-search",
            "mcp-server-code-runner",
            "notion",
            "slack",
            "google-workspace",
            "mongodb",
            "airtable",
            "github",
            "wikipedia",
        )
    },
    "desktop-commander": desktop_commander,
}


def build_mcp_servers(task_dir: Path, workdir: str) -> list:
    """The MCP arm: upstream's own app, serving the servers this task needs.

    Atlas's harness never reaches a server. It reaches one HTTP app,
    `agent_environment/main.py`, which hands every server it is configured
    with to one fastmcp client -- prefixing each tool with its server's key,
    answering a repeated call to a cacheable server from its cache, and
    turning a failure into a `{"detail": ...}` error -- and the harness keeps
    the tools the row enables (`sandbox-client.ts:115`). So the arm is that
    app, in the run's container, with nothing of this repo's between it and
    the harness.

    Args:
        task_dir (Path): the task directory.
        workdir (str): the run's workspace, which the app never sees.

    Returns:
        list: one `Sandbox`, not yet started.
    """
    return [Sandbox(task_dir.name)]


class Sandbox:
    """Upstream's app, started in the run's container on entry.

    Attributes:
        name (str): what the arm reports it as.
        url (str): the app's address from this machine, once started.
    """

    name = "agent-environment"

    def __init__(self, task: str):
        self.task = task
        self.url = ""
        self.stack = ExitStack()

    async def __aenter__(self):
        # In the template's order, which is the order upstream's config keeps
        # its servers in, fastmcp lists their tools in, and so the order of
        # the tools the model is sent.
        needed = needed_mcp_servers(self.task)
        servers = {name: spec(name) for name in template() if name in needed}
        self.url = await asyncio.to_thread(app, servers, self.stack)
        return self

    async def __aexit__(self, *exc):
        self.stack.close()

    async def list_tools(self) -> list:
        """The tools the harness will advertise, for the arm's report.

        Returns:
            list: the app's tools that the row enables.
        """
        import httpx

        enabled = set(enabled_tools(self.task))
        async with httpx.AsyncClient(timeout=None) as http:
            listed = await http.post(f"{self.url}/list-tools")
        listed.raise_for_status()
        return [tool for tool in listed.json() if tool["name"] in enabled]


# The app's port, and the command the image runs it with (`Dockerfile`'s
# CMD). The image's entrypoint, which `envsubst`s the template into the
# config before that command, is left out, because the config is written
# whole here.
PORT = 1984
APP = ("uv", "run", "python", "-m", "uvicorn", "agent_environment.main:app",
       "--host", "0.0.0.0", "--port", str(PORT))
CONFIG = "src/agent_environment/mcp_server_config.json"

# How long the app may take to answer once started: what the harness itself
# waits for it (`sandbox-client.ts:92`, 90 tries 2 s apart).
APP_START = 180


def app(servers: dict, stack: ExitStack) -> str:
    """Start upstream's app in the run's container, serving `servers`.

    The config goes where the entrypoint would have written its own, and
    `ENABLED_SERVERS` names every server in it: the app's other mode keeps
    only the servers whose template keys are in its own environment, which
    this repo passes to no process but the server that reads each.

    Args:
        servers (dict): `mcpServers`, keyed as the template keys them.
        stack (ExitStack): stops the app when the run ends.

    Returns:
        str: the app's address from this machine.

    Raises:
        RuntimeError: the app exited, or did not answer in time.
    """
    name = container()
    subprocess.run([
        "docker", "exec", "--interactive", "--workdir", WORKDIR, name, "sh",
        "-c", f"cat > {CONFIG}"
    ],
                   input=json.dumps({
                       "mcpServers": servers
                   }).encode(),
                   check=True)
    path = logs() / "agent-environment.log"
    log = stack.enter_context(path.open("w"))
    process = subprocess.Popen([
        "docker", "exec", "--workdir", WORKDIR, "--env", "ENABLED_SERVERS",
        name, *APP
    ],
                               env={
                                   **os.environ, "ENABLED_SERVERS":
                                   ",".join(servers)
                               },
                               stdout=log,
                               stderr=subprocess.STDOUT)
    stack.callback(process.wait)
    stack.callback(process.terminate)
    published = subprocess.run(["docker", "port", name, f"{PORT}/tcp"],
                               capture_output=True,
                               text=True,
                               check=True).stdout.split()[0]
    url = f"http://{published}"
    deadline = time.monotonic() + APP_START
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{NAME}: the app exited "
                               f"({process.returncode}); see {path}")
        try:
            with urllib.request.urlopen(url, timeout=5):
                return url
        except OSError:
            time.sleep(1)
    raise RuntimeError(f"{NAME}: the app did not answer in {APP_START} s; "
                       f"see {path}")


def logs() -> Path:
    """Where this run's app and harness write their logs.

    Beside the run's workspace rather than in it, since the mirage arm
    mounts the workspace and a log in it would be the model's to read.

    Returns:
        Path: the directory, created.
    """
    path = Path(os.environ["AGENT_WORKSPACE"] + ".logs")
    path.mkdir(parents=True, exist_ok=True)
    return path


def expose(url: str, stack: ExitStack) -> str:
    """`url` from inside the run's container, checked to be reachable.

    The services listen on this machine's loopback, which the container
    reaches at `host.docker.internal` on Docker Desktop. A Linux engine has
    no such name, so there the container is given its gateway, and each port
    it needs is relayed from the gateway to the loopback.

    Args:
        url (str): the service, as this machine reaches it.
        stack (ExitStack): stops the relay when the run ends.

    Returns:
        str: the same service from inside the container.

    Raises:
        SystemExit: the container cannot reach it.
    """
    host = os.environ["MCPATLAS_HOST"]
    if host != "host.docker.internal":
        relay(host, urlsplit(url).port, stack)
    inner = urlsplit(reach(url))
    if subprocess.run([
            "docker", "exec",
            container(), "python3", "-c", "import socket, sys; "
            "socket.create_connection((sys.argv[1], sys.argv[2]), 10)",
            inner.hostname,
            str(inner.port)
    ],
                      capture_output=True).returncode != 0:
        raise SystemExit(f"{NAME}: the container cannot reach {url} "
                         f"at {inner.netloc}")
    return inner.geturl()


def local(task: str) -> Path:
    """Where this repo keeps one task's files.

    Args:
        task (str): the task name.

    Returns:
        Path: the directory, whether or not it exists.
    """
    return REPO_ROOT.joinpath(*LOCAL, task)


def tasks() -> list[str]:
    """Every task this repo carries.

    Returns:
        list[str]: task directory names, sorted.
    """
    pool = REPO_ROOT.joinpath(*LOCAL)
    return sorted(d.name for d in pool.iterdir()
                  if (d / "shared" / "task.md").is_file())


def seeder() -> Path:
    """What rebuilds this dataset's fixtures before a draw.

    Not the shared `server/seed/seed_task.py`: that one dispatches Toolathlon's
    fixture kinds and cross-checks the manifest against upstream's
    `task_config.json`, neither of which exists here. An Atlas fixture is one
    tree, the pinned image's `/data`, copied into a fresh per-run workspace,
    so this dataset's seeder only has to copy it out of the image.

    Returns:
        Path: the seeder, run once per arm.
    """
    return REPO_ROOT.joinpath(*SEEDER)


def manifest(task: str) -> Path:
    """The fixture manifest.

    Args:
        task (str): the task name.

    Returns:
        Path: the manifest, which may not exist.
    """
    return local(task).joinpath(*MANIFEST)


def declaration(task: str) -> dict:
    """The dataset row this task was cut from.

    Args:
        task (str): the task name.

    Returns:
        dict: `task`, `enabled_tools` and `claims`, as upstream wrote them.
    """
    return json.loads(local(task).joinpath(*DECLARATION).read_text())


def enabled_tools(task: str) -> list[str]:
    """The tools Atlas gives this task, by their model-facing names.

    The unit is the *tool*, not the server, which is the sharpest difference
    between the two datasets: Toolathlon names servers and takes every tool
    they expose, while Atlas hands each task a hand-picked subset -- ten of
    the filesystem server's fourteen here, four of the code executor's nine.
    Advertising the other nine would hand this arm a surface upstream never
    gave it, and tool definitions are re-sent on every request, so it would
    show up as tokens.

    Args:
        task (str): the task name.

    Returns:
        list[str]: model-facing tool names, in upstream's order.
    """
    return list(declaration(task)["enabled_tools"])


# The tools through which the MCP arm reaches what each mount shows. A mount
# holds the whole of its service, where that arm reaches only what the tools
# Atlas enables for the task read, and a mount beyond them is a way to the
# answer the other arm never had. So a task mounts a service only when it
# enables a tool from each set here, and otherwise reaches it through its
# tool-command CLI alone, as the MCP arm does.
MOUNT_READERS = {
    # Pages found by title, and a page's body, which `page.json` holds.
    "/notion": ({"notion_API-post-search"}, {"notion_API-get-block-children"}),
    # A channel's messages, by its ID or `#name`, or a search across them.
    "/slack":
    ({"slack_conversations_history", "slack_conversations_search_messages"}, ),
    # The bases' IDs, then a table's records.
    "/airtable": ({"airtable_list_bases"},
                  {"airtable_list_records", "airtable_search_records"}),
    "/mongodb": ({"mongodb_find", "mongodb_aggregate"}, ),
    "/calendar": ({"google-workspace_list_events"}, ),
    # Any file of /data, through a server that reads one or runs code beside
    # it. E2B runs code in its own cloud sandbox, which cannot see /data.
    "/data": ({
        "filesystem_read_file", "filesystem_read_text_file",
        "filesystem_read_multiple_files", "filesystem_read_media_file",
        "desktop-commander_read_file", "desktop-commander_read_multiple_files",
        "cli-mcp-server_run_command", "mcp-code-executor_execute_code",
        "mcp-server-code-runner_run-code"
    }, ),
    # A repository, where nothing reads the rest of /data: every git tool
    # reads one, even its status, which names the commit HEAD is at.
    "/data/repos": ({
        "git_git_status", "git_git_log", "git_git_show", "git_git_diff",
        "git_git_diff_staged", "git_git_diff_unstaged"
    }, ),
}


def readable(task: str, mount: str) -> bool:
    """Whether the tools a task enables read what a mount shows.

    Args:
        task (str): the task name.
        mount (str): a key of `MOUNT_READERS`.

    Returns:
        bool: True when the task enables a tool from each of its sets.
    """
    enabled = set(enabled_tools(task))
    return all(enabled & tools for tools in MOUNT_READERS[mount])


def needed_mcp_servers(task: str) -> list[str]:
    """The MCP servers this task needs, derived from its tool list.

    Atlas never names servers -- the sandbox at :1984 aggregates all of them
    and the task filters by tool name (`sandbox-client.ts:115`). So the server
    set is whatever the enabled tools imply, and it is read off the same
    declaration rather than restated, for the reason every other list in this
    repo is read rather than restated.

    Args:
        task (str): the task name.

    Returns:
        list[str]: server names, in first-appearance order.
    """
    return list(dict.fromkeys(server_of(tool) for tool in enabled_tools(task)))


def needed_local_tools(task: str) -> list[str]:
    """The local tools this dataset gives a task, which is none.

    Atlas has no local-tool layer: everything the agent can do arrives over
    MCP, including the Python interpreter, which is the `mcp-code-executor`
    server rather than Toolathlon's in-process `python_execute`.

    Args:
        task (str): the task name.

    Returns:
        list[str]: always empty.
    """
    return []


def prompt(task: str) -> Path | None:
    """The system prompt the MCP arm is given, which for Atlas is none.

    `run_eval.py` sends the task alone unless given `--system-prompt`, and
    the harness prepends an *empty* system message only when the model is
    literally `openai/gpt-5` (`litellm-strategy.ts:134`) -- which it does
    here too, being upstream's. None rather than a path to an empty file,
    which committed next to the task would read as an oversight where this
    is a decision.

    Args:
        task (str): the task name, unused.

    Returns:
        Path | None: None, since the dataset sends none.
    """
    return None


def pinned() -> str:
    """The commit `submodule/mcp-atlas` is pinned to.

    Read from the superproject's gitlink at HEAD, not from the submodule's own
    HEAD -- the same reason `mcp_servers.upstream_config` reads `git show
    HEAD:`. A checkout can be left on some other commit, and this tree is what
    the model reads, so a submodule nobody meant to move would change the
    measured bytes with nothing to show for it.

    Returns:
        str: the full sha.

    Raises:
        SystemExit: HEAD records no gitlink there.
    """
    where = "/".join(SUBMODULE)
    found = subprocess.run(
        ["git", "-C",
         str(REPO_ROOT), "rev-parse", f"HEAD:./{where}"],
        capture_output=True,
        text=True,
        check=False)
    if found.returncode != 0:
        raise SystemExit(f"{NAME}: HEAD records no gitlink for {where}: "
                         f"{found.stderr.strip()}")
    return found.stdout.strip()


def image_id() -> str:
    """The pinned image's id on this machine, pulled if it is not here.

    The pin is a multi-platform index, and the id is of the one image this
    machine runs -- which matters for `/data`, since the code executor's
    venv in it is built per platform.

    Returns:
        str: the id, without its `sha256:`.
    """
    inspect = ["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE]
    found = subprocess.run(inspect, capture_output=True, text=True)
    if found.returncode != 0:
        subprocess.run(["docker", "pull", "--quiet", IMAGE],
                       stdout=subprocess.DEVNULL,
                       check=True)
        found = subprocess.run(inspect,
                               capture_output=True,
                               text=True,
                               check=True)
    return found.stdout.strip().removeprefix("sha256:")


def environment() -> Path:
    """The mirage arm's copy of the image's `/data`, under `state/`.

    Keyed by the image, so two images never share a directory and a new pin
    copies a new tree rather than editing an old one. Under `state/` because
    it is derived and gitignored: `rm -rf state/` is this repo's start-clean
    move, and the next seed puts it back.

    Returns:
        Path: the directory, which `build_environment` fills.
    """
    return REPO_ROOT / "state" / NAME / f"image-{image_id()[:12]}" / "data"


def build_environment() -> list[str]:
    """Copy the pinned image's `/data` out, whole, once per image.

    Every file, recursively, with its mode, its time and its symlinks as
    they are -- the CSVs, the clones at the refs they had when the image was
    built, and the code executor's venv -- exactly the tree the container
    serves the MCP arm. No filter of any kind: a tree cut down to the files
    a task happens to need would give the model a listing Atlas never showed
    it. Written beside the target and renamed into place, so a copy cut
    short is never taken for one that finished.

    Returns:
        list[str]: the tree's own files, as `tree_files` lists them.

    Raises:
        SystemExit: the copy failed.
    """
    into = environment()
    if not into.is_dir():
        into.parent.mkdir(parents=True, exist_ok=True)
        created = subprocess.run(["docker", "create", IMAGE],
                                 capture_output=True,
                                 text=True,
                                 check=True).stdout.strip()
        try:
            with tempfile.TemporaryDirectory(dir=into.parent) as scratch:
                copy = subprocess.Popen(
                    ["docker", "cp", f"{created}:/data", "-"],
                    stdout=subprocess.PIPE)
                unpacked = subprocess.run(
                    ["tar", "-x", "-p", "-f", "-", "-C", scratch],
                    stdin=copy.stdout,
                    check=False)
                copy.stdout.close()
                if copy.wait() != 0 or unpacked.returncode != 0:
                    raise SystemExit(f"{NAME}: could not copy /data out of "
                                     f"{IMAGE}")
                os.replace(Path(scratch) / "data", into)
        finally:
            subprocess.run(["docker", "rm", created],
                           capture_output=True,
                           check=False)
    return tree_files(into)


# The repositories the image's Dockerfile clones into `repos/`, one per row
# (`Dockerfile:23-29`), and the venv it syncs for the code executor.
CLONES = ("repos", "git_submodule_info.csv")
VENV = PurePosixPath("repos", "mcp_code_executor_workspace", ".venv")


def clones() -> list[str]:
    """Where the image's Dockerfile clones each repository.

    Read from upstream's list at the pinned commit, as `template` reads the
    server config, since the Dockerfile clones one repository per row of it.

    Returns:
        list[str]: each clone's path, under `/data/repos`.
    """
    shown = at_pin("/".join(("services/agent-environment/data", *CLONES)))
    shown.check_returncode()
    return [
        row.split(",", 2)[2] for row in shown.stdout.splitlines()
        if row.strip()
    ]


def tree_files(into: Path) -> list[str]:
    """The tree's own files, leaving out the clones and the venv.

    Args:
        into (Path): the copied tree.

    Returns:
        list[str]: paths relative to the tree, sorted.
    """
    apart = {VENV} | {
        PurePosixPath(row.split(",", 2)[2]).relative_to("/data")
        for row in into.joinpath(*CLONES).read_text().splitlines()
        if row.strip()
    }
    return sorted(
        str(p.relative_to(into)) for p in into.rglob("*")
        if p.is_file() and not any(
            PurePosixPath(p.relative_to(into)).is_relative_to(c)
            for c in apart))


# The servers the mirage arm reaches through a tool-command CLI, `<server>
# <tool>` for the MCP arm's `<server>_<tool>`: a knowledge graph's search, a
# page fetched and turned into markdown, a weather service's own queries, the
# live services Atlas enables beside a task as distractors, and Notion,
# Slack, MongoDB, Calendar and Airtable. Those are mounts as well where the
# task's tools read them (`MOUNT_READERS`), but their tools are the MCP arm's
# exactly, rather than Notion's `ntn` or mirage's `slack` or `airtable`, each
# of which reaches far more of its service than Atlas enables; `notion` drops
# the `API-` its server's generated names carry, so `notion_API-post-search`
# is `notion post-search`. `gh` and `git` stay native. Each is keyed by
# server, with the variable its CLI reads the transport's address from and
# the spec a task's yaml points that CLI at.
TOOL_COMMANDS = {
    "notion": ("NOTION_CLI_URL", "cli/mcpatlas/tools.mjs:NOTION"),
    "slack": ("SLACK_CLI_URL", "cli/mcpatlas/tools.mjs:SLACK"),
    "memory": ("MEMORY_CLI_URL", "cli/mcpatlas/tools.mjs:MEMORY"),
    "fetch": ("FETCH_CLI_URL", "cli/mcpatlas/tools.mjs:FETCH"),
    "weather": ("WEATHER_CLI_URL", "cli/mcpatlas/tools.mjs:WEATHER"),
    "e2b-server": ("E2B_SERVER_CLI_URL", "cli/mcpatlas/tools.mjs:E2B"),
    "met-museum": ("MET_MUSEUM_CLI_URL", "cli/mcpatlas/tools.mjs:MET_MUSEUM"),
    "national-parks":
    ("NATIONAL_PARKS_CLI_URL", "cli/mcpatlas/tools.mjs:NATIONAL_PARKS"),
    "clinicaltrialsgov-mcp-server":
    ("CLINICAL_TRIALS_CLI_URL", "cli/mcpatlas/tools.mjs:CLINICAL_TRIALS"),
    "whois": ("WHOIS_CLI_URL", "cli/mcpatlas/tools.mjs:WHOIS"),
    "context7": ("CONTEXT7_CLI_URL", "cli/mcpatlas/tools.mjs:CONTEXT7"),
    "oxylabs": ("OXYLABS_CLI_URL", "cli/mcpatlas/tools.mjs:OXYLABS"),
    "arxiv": ("ARXIV_CLI_URL", "cli/mcpatlas/tools.mjs:ARXIV"),
    "weather-data":
    ("WEATHER_DATA_CLI_URL", "cli/mcpatlas/tools.mjs:WEATHER_DATA"),
    "pubmed": ("PUBMED_CLI_URL", "cli/mcpatlas/tools.mjs:PUBMED"),
    "exa": ("EXA_CLI_URL", "cli/mcpatlas/tools.mjs:EXA"),
    "wikipedia": ("WIKIPEDIA_CLI_URL", "cli/mcpatlas/tools.mjs:WIKIPEDIA"),
    "open-library":
    ("OPEN_LIBRARY_CLI_URL", "cli/mcpatlas/tools.mjs:OPEN_LIBRARY"),
    "calculator": ("CALCULATOR_CLI_URL", "cli/mcpatlas/tools.mjs:CALCULATOR"),
    "google-maps": ("GOOGLE_MAPS_CLI_URL",
                    "cli/mcpatlas/tools.mjs:GOOGLE_MAPS"),
    "osm-mcp-server": ("OSM_CLI_URL", "cli/mcpatlas/tools.mjs:OSM"),
    "ddg-search": ("DDG_SEARCH_CLI_URL", "cli/mcpatlas/tools.mjs:DDG_SEARCH"),
    "mongodb": ("MONGODB_CLI_URL", "cli/mcpatlas/tools.mjs:MONGODB"),
    "google-workspace": ("GOOGLE_WORKSPACE_CLI_URL",
                         "cli/mcpatlas/tools.mjs:GOOGLE_WORKSPACE"),
    "airtable": ("AIRTABLE_CLI_URL", "cli/mcpatlas/tools.mjs:AIRTABLE"),
    "mcp-server-code-runner": ("CODE_RUNNER_CLI_URL",
                               "cli/mcpatlas/tools.mjs:CODE_RUNNER"),
}


@contextmanager
def services(task: str, workdir: str):
    """Serve a task's container, fakes and tool-command CLIs, for either arm.

    The container first: upstream's image, fresh for this run, which every
    server of either arm is started in -- so a write of one run's, or a
    config a launch leaves, is gone with it, as each Atlas sandbox is.

    Then the fakes: Notion, Slack, Calendar and Airtable, each a process of
    this run's seeded with Atlas's workspace or base, and GitHub, one that
    holds nothing, for a task not in `GITHUB_LIVE`; slack.com,
    googleapis.com, api.airtable.com and api.github.com answered by theirs;
    and MongoDB, a container of this run's restored from Atlas's dump. The
    variables upstream's template reads are set to name the fakes' tenant,
    so the MCP arm's builders read them as upstream's config does; the
    mirage arm's yaml names the same fakes.

    Then the CLIs. Each is the server the MCP arm runs -- this seam's
    builder, the same workspace -- with the transport as its client instead
    of the model's loop, and the same filter on top: the CLI lists and calls
    the tools Atlas's row enables and no others, since a command the other
    arm was never given is surface the other arm was never measured on.

    Args:
        task (str): the task name.
        workdir (str): the run's workspace, already seeded.

    Yields:
        None: while the fakes and transports are up.
    """
    import yaml
    sys.path.insert(0, str(REPO_ROOT))
    from server.mcp.mcp_servers import Launch
    from server.seed.travel_video import client_thread

    config = local(task) / "vfs" / "workspace.yaml"
    clis = (yaml.safe_load(config.read_text())
            or {}).get("clis") or {} if config.is_file() else {}
    kinds = [
        kind for kind, (_, spec) in TOOL_COMMANDS.items()
        if str(clis.get(kind, {}).get("cli", "")).endswith(spec)
    ]
    enabled = enabled_tools(task)
    needed = needed_mcp_servers(task)
    with ExitStack() as stack:

        def export(variable: str, value: str) -> None:
            """Set one variable for the run, and put it back after."""
            previous = os.environ.get(variable)
            stack.callback(lambda: os.environ.pop(variable) if previous is None
                           else os.environ.update({variable: previous}))
            os.environ[variable] = value

        from server.mcp.setup_mcpatlas import image_name
        image = image_name()
        if subprocess.run(["docker", "image", "inspect", image],
                          capture_output=True).returncode != 0:
            raise SystemExit(f"{NAME}: no image {image}; run `{SETUP}`")
        name = f"vfs-bench-mcpatlas-{os.getpid()}-{time.monotonic_ns()}"
        subprocess.run([
            "docker", "run", "--detach", "--rm", "--init", "--name", name,
            "--publish", f"127.0.0.1::{PORT}", "--entrypoint", "sleep", image,
            "infinity"
        ],
                       stdout=subprocess.DEVNULL,
                       check=True)
        stack.callback(subprocess.run, ["docker", "rm", "--force", name],
                       capture_output=True)
        export("MCPATLAS_CONTAINER", name)

        # The address `expose` hands the container for this machine.
        export("MCPATLAS_HOST", bridge(name) or "host.docker.internal")

        def copy_in(source: str, target: str) -> None:
            """Copy a file of this machine's into the run's container."""
            subprocess.run(["docker", "cp", source, f"{name}:{target}"],
                           check=True)

        def intercept(url: str, ca: str, *hosts: str) -> tuple[str, str]:
            """Answer a server's requests to `hosts` with the fake at `url`.

            Returns:
                tuple[str, str]: the proxy, from inside the container, and
                    where in it the certificate the server has to trust is.
            """
            host = stack.enter_context(slack_host.serve(url, *hosts))
            authority = f"/opt/vfs-bench/{ca}"
            copy_in(host["ca"], authority)
            return expose(host["proxy"], stack), authority

        faked = {
            "notion", "slack", "google-workspace", "mongodb", "airtable",
            "github"
        }
        if faked & set(needed):
            from server.fakes import slack_host
            from server.seed import atlas_exports as fixtures
        if "notion" in needed:
            export("NOTION_URL", fixtures.fake("notion", stack))
            export("NOTION_TOKEN", fixtures.TENANT)
            expose(os.environ["NOTION_URL"], stack)
        if "slack" in needed:
            export("SLACK_URL", fixtures.fake("slack", stack))
            export("SLACK_MCP_XOXC_TOKEN", f"xoxc-{fixtures.TENANT}")
            export("SLACK_MCP_XOXD_TOKEN", f"xoxd-{fixtures.TENANT}")
            proxy, authority = intercept(os.environ["SLACK_URL"], "slack.pem")
            export("SLACK_MCP_PROXY", proxy)
            export("SLACK_MCP_SERVER_CA", authority)
        if "google-workspace" in needed:
            from server.clients import gws
            export("CALENDAR_URL", fixtures.fake("calendar", stack))
            for variable in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
                export(variable, fixtures.TENANT)
            export("GOOGLE_REFRESH_TOKEN", gws.TOKEN)
            proxy, authority = intercept(os.environ["CALENDAR_URL"],
                                         "googleapis.pem",
                                         "www.googleapis.com",
                                         "oauth2.googleapis.com")
            export("GOOGLE_WORKSPACE_PROXY", proxy)
            export("GOOGLE_WORKSPACE_CA", authority)
        if "airtable" in needed:
            export("AIRTABLE_URL", fixtures.fake("airtable", stack))
            export("AIRTABLE_API_KEY", fixtures.airtable_token())
            proxy, authority = intercept(os.environ["AIRTABLE_URL"],
                                         "airtable.pem", "api.airtable.com")
            export("AIRTABLE_PROXY", proxy)
            export("AIRTABLE_CA", authority)
        if "github" in needed and task not in GITHUB_LIVE:
            export("GITHUB_URL", fixtures.fake("github", stack))
            export("GITHUB_TOKEN", fixtures.TENANT)
            export("GITHUB_API_URL", expose(os.environ["GITHUB_URL"], stack))
            copy_in(str(REPO_ROOT / "redirect/github/github_hook.mjs"),
                    GITHUB_HOOK)
        if "mongodb" in needed:
            export("MONGODB_URL", fixtures.mongo(stack))
            export("MONGODB_CONNECTION_STRING",
                   expose(os.environ["MONGODB_URL"], stack))
        directory = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        for kind in kinds:
            variable = TOOL_COMMANDS[kind][0]
            endpoint = directory / f"{kind}.endpoint"
            logpath = directory / f"{kind}.log"
            log = stack.enter_context(logpath.open("w"))
            params = SERVERS[kind](Launch(task_dir=local(task),
                                          workdir=workdir))
            tools = {
                tool.split("_", 1)[1]
                for tool in enabled if server_of(tool) == kind
            }
            thread, close = client_thread(kind,
                                          endpoint,
                                          params,
                                          log,
                                          tools=tools)
            stack.callback(close)
            # As long as the app may take: each is its servers started again,
            # in the same container, while other runs start theirs.
            for _ in range(APP_START * 10):
                if endpoint.exists():
                    export(variable, endpoint.read_text())
                    break
                if not thread.is_alive():
                    raise RuntimeError(logpath.read_text())
                time.sleep(.1)
            else:
                raise TimeoutError(f"{NAME}: the {kind} CLI did not start: "
                                   f"{logpath.read_text()}")
        yield


def initial_workspace(task: str) -> Path:
    """The starting tree the mirage arm mounts at `/data`.

    Every task's is the same one, because Atlas has one environment image and
    not a fixture per task, so the task name is taken for the seam's shape and
    ignored. The MCP arm's servers read the image's own, which is the same.

    Args:
        task (str): the task name, unused.

    Returns:
        Path: the directory, which `script/seed_task.py` builds.
    """
    return environment()


def managed_workspace_paths(task: str) -> set[PurePosixPath]:
    """The part of the tree the generic copy into a workspace leaves alone.

    The code executor's venv, whose interpreter is an absolute link into the
    image it was built in: the generic copy follows links, and this one
    resolves to nothing outside the image. `prepare_workspace` copies it.

    Args:
        task (str): the task name, unused.

    Returns:
        set[PurePosixPath]: the venv, relative to the tree.
    """
    return {VENV}


def prepare_workspace(task: str, workspace: Path) -> None:
    """Copy the venv in, its links as links, as the image has them.

    Each file is a clone where the volume can make one (`server.clone`),
    for the venv is 212 of the tree's 250 MB.

    Args:
        task (str): the task name, unused.
        workspace (Path): the run's workspace, the rest of the tree copied.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from server.clone import clone

    target = workspace / VENV
    if not target.exists():
        shutil.copytree(environment() / VENV,
                        target,
                        symlinks=True,
                        copy_function=clone)


def evaluator(task: str) -> Path:
    """What grades a run.

    Atlas ships no evaluator. It scores the agent's final message against the
    row's `GTFA_CLAIMS`, so the claims file *is* the evaluator's input, and
    `script/grade_task.py` is what reads it.

    Args:
        task (str): the task name.

    Returns:
        Path: the claims file, which is what has to exist for a grade.
    """
    return local(task).joinpath(*DECLARATION)


def server_of(tool: str) -> str:
    """The server a model-facing tool name belongs to.

    `servername_toolname`, splitting on the first underscore, which is
    `agent_environment/main.py:221` exactly. Server names keep their hyphens
    -- `mcp-code-executor_execute_code`, not `mcp_code_executor_execute_code`
    -- so this is not Toolathlon's convention and must not be run through it.

    Args:
        tool (str): the model-facing tool name.

    Returns:
        str: the server name.
    """
    return tool.split("_", 1)[0]


def shown_tool_name(server: str, tool: str) -> str:
    """The name Atlas shows the model, from the two names a server has.

    The sandbox composes its servers with fastmcp, which prefixes each tool
    with its config key and an underscore and changes nothing else. Toolathlon
    additionally rewrites hyphens to underscores; Atlas does not, and the
    difference is visible in the dataset's own tool lists, which spell
    `mcp-code-executor_execute_code` with the server's hyphens intact.

    Two arguments rather than one joined name, because a hyphen cannot both
    join the pair and appear inside the server name: `mcp-code-executor` plus
    `execute_code` has no unambiguous single spelling to take apart again.

    Args:
        server (str): the server name.
        tool (str): the tool's own name.

    Returns:
        str: the model-facing name.
    """
    return f"{server}_{tool}"
