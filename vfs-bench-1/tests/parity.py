#!/usr/bin/env python
import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import NamedTuple
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "agent"))
sys.path.insert(0, str(REPO_ROOT / "task"))
sys.path.insert(0, str(REPO_ROOT / "server" / "mcp"))
sys.path.insert(0, str(REPO_ROOT / "server" / "clients"))

# The same seam `arms.py`, `grading.py` and `mcp_servers.py` read a task
# through. Every path this file used to spell out -- the case file, the
# task directory, the dataset's own seeder -- has an accessor here, so
# the benchmark is named once rather than in four places.
import dataset  # noqa: E402

# The behaviour half of the fidelity question, made executable.
#
# That the two arms are *offered* the same tools says nothing about what
# those tools return. This runs one logical operation down both arms over
# one fixture and compares the answers -- the MCP arm through its real
# upstream server, the mirage arm through `ws.execute`, which is the single
# shell tool its agent gets.
#
# A case that mutates is run twice from a fresh seed, once per arm, and both
# the returned document and the resulting fixture state are compared. That
# is what catches a fake that succeeds wrongly: the two arms can agree on a
# reply and still leave different rows behind.
#
# A case may be `known` to diverge, and then says with `expect` which lines
# the divergence produces; a line no pattern covers fails the case like any
# other. A skipped case fails the gate: it proved nothing.
#
# Cases live in `task/toolathlon/<task>/tests/parity.json` so a task's
# tests sit with the task. The two sides are spelled `mcp` and `mirage`
# rather than "api", because the mirage arm reaches a service by whichever
# route it has -- a
# CLI, a mount, or `server/api/` -- and the test should not care which.

CASES = "tests/parity.json"

# `--show`: print what each arm answered, projected, so an agreement can be
# read as well as counted -- two arms that agree on an error have agreed on
# nothing.
SHOW = False


def load(task: str) -> dict | None:
    """Read one task's parity cases.

    Args:
        task (str): the task directory name.

    Returns:
        dict | None: the parsed file, or None when the task declares none.
    """
    path = dataset.local(task) / CASES
    if not path.is_file():
        return None
    spec = json.loads(path.read_text(encoding="utf-8"))
    for case in spec["cases"]:
        if case.get("known") and not case.get("expect"):
            raise SystemExit(f"parity: {task}/{case['name']} is `known` "
                             f"without `expect`; say which lines the "
                             f"divergence produces")
        for pattern in case.get("expect", []):
            try:
                re.compile(pattern)
            except re.error as bad:
                raise SystemExit(f"parity: {task}/{case['name']}: `expect` "
                                 f"pattern {pattern!r} does not compile: "
                                 f"{bad}") from None
    return spec


def seed(task: str) -> None:
    """Rebuild the task's fixture, so a case starts from a known state.

    Args:
        task (str): the task directory name.

    Raises:
        Unseedable: seeding failed. Never swallowed -- a case run against a
            fixture that did not rebuild is comparing two arms over
            whatever the last run left behind.
    """
    done = subprocess.run(
        [sys.executable, str(dataset.seeder()), task],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True)
    if done.returncode != 0:
        tail = (done.stdout + done.stderr).strip().splitlines()
        raise Unseedable(tail[-2] if len(tail) > 1 else (tail or ["?"])[-1])
    # Seeding a BigQuery fixture starts the emulator and republishes its
    # endpoints and project, so what this process is holding from the
    # previous task is now stale. Overriding, for the same reason
    # `run_agent.py` does: the file is the newer of the two.
    import services
    services.load_stack_env(override=True)
    # The runner builds the initial workspace after seeding. Do the same
    # here, including task preprocessing, after every mutating-case reset.
    import arms
    arms.build_workspace_dir(dataset.local(task))


class Unseedable(Exception):
    """A task's fixture could not be rebuilt, so its cases cannot run.

    Almost always a service that is not up or not pointed at this task.
    Reported as a skip with the seeder's own reason rather than a hard
    stop, so one such task does not hide the others -- counted separately
    from a pass, and failing the gate. It did not always: a run with the
    whole stack down once skipped every case and exited 0, which is the
    one thing a gate must not do.
    """


class ProjectionError(Exception):
    """A case's jq filter did not fit the reply it was pointed at."""


def projected(text: str,
              filter_: str | None,
              raw: bool = False,
              pipe: str | None = None) -> str:
    """Narrow one arm's raw reply to the part the case compares.

    The two surfaces answer in their own shapes -- the MCP tool returns
    `{spreadsheetId, valueRanges}` where the mount returns the whole
    `spreadsheets.get` document -- so a case says, for each side, which jq
    filter reaches the same fact. Both sides get the same mechanism, so the
    projection is readable next to what it projects rather than buried in
    one arm's command line.

    Args:
        text (str): the raw reply.
        filter_ (str | None): a jq filter, or None to compare as-is.
        raw (bool): emit bare strings rather than JSON ones, so a side that
            naturally answers in lines (`ls`, a CLI's one-row-per-line
            output) can be compared against a side that answers in JSON.
        pipe (str | None): a shell pipeline to send the reply through
            instead of jq. Some servers answer in prose -- the `emails`
            server reports "1. INBOX (3 total, 0 unread)" where a legacy
            CLI returned JSON -- and a fact in prose needs `sed`, not a JSON
            path. Takes precedence over `filter_`.

    Returns:
        str: the projected text.

    Raises:
        ProjectionError: jq refused the input, which means the case's
            filter and the arm's actual reply shape disagree -- usually
            because the arm returned an error document. Raised rather than
            exited on, so one mis-specified case fails alone instead of
            taking the suite down with it.
    """
    if pipe:
        argv, what = ["bash", "-c", pipe], pipe
    elif filter_:
        argv, what = ["jq", "-r" if raw else "-c", filter_], f"jq {filter_!r}"
    else:
        return text
    done = subprocess.run(argv, input=text, capture_output=True, text=True)
    if done.returncode != 0:
        raise ProjectionError(f"{what} failed: {done.stderr.strip()} "
                              f"-- on {text[:300]!r}")
    return done.stdout.strip()


def decoded(text: str) -> object:
    """Parse a tool's reply as JSON where it is JSON, else keep the text.

    Both arms return a single document per call, but not every tool returns
    JSON -- some return a human-readable line. Comparing parsed JSON rather
    than bytes is what lets key order and whitespace differ without being
    reported as a divergence.

    Args:
        text (str): the raw reply.

    Returns:
        object: the parsed value, or the original string.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def pruned(value: object, drop: list[str]) -> object:
    """Remove keys a case declares unstable, at any depth.

    Args:
        value (object): a decoded reply or state snapshot.
        drop (list[str]): key names to remove.

    Returns:
        object: the same structure without those keys.
    """
    if isinstance(value, dict):
        return {
            key: pruned(inner, drop)
            for key, inner in value.items() if key not in drop
        }
    if isinstance(value, list):
        return [pruned(item, drop) for item in value]
    return value


def difference(left: object, right: object, path: str = "") -> list[str]:
    """Describe where two decoded replies stop agreeing.

    A diff rather than a bare unequal, because "the two arms disagree" is
    not actionable and "the mirage arm omits `spreadsheetUrl`" is.

    Args:
        left (object): the MCP arm's value.
        right (object): the mirage arm's value.
        path (str): dotted position, for the message.

    Returns:
        list[str]: one line per disagreement, empty when they match.
    """
    where = path or "<root>"
    if type(left) is not type(right):
        return [
            f"{where}: mcp is {type(left).__name__}, "
            f"mirage is {type(right).__name__}"
        ]
    if isinstance(left, dict):
        out = []
        for key in sorted(set(left) | set(right)):
            if key not in left:
                out.append(f"{where}.{key}: only mirage has it")
            elif key not in right:
                out.append(f"{where}.{key}: only mcp has it")
            else:
                out += difference(left[key], right[key], f"{where}.{key}")
        return out
    if isinstance(left, list):
        if len(left) != len(right):
            return [
                f"{where}: mcp has {len(left)} item(s), "
                f"mirage has {len(right)}"
            ]
        out = []
        for index, (one, two) in enumerate(zip(left, right)):
            out += difference(one, two, f"{where}[{index}]")
        return out
    if left != right:
        return [f"{where}: mcp {left!r} != mirage {right!r}"]
    return []


def gws_state(task_dir: Path) -> dict:
    """Everything the fake Google Workspace holds, as one comparable value.

    Every file, and for each spreadsheet every tab and every cell. The
    point is to catch an arm that returned the right document and wrote the
    wrong rows.

    Args:
        task_dir (Path): the task directory; unused, the fake is shared.

    Returns:
        dict: files keyed by id, each with its spreadsheet contents.
    """
    import gws

    files = gws.call("GET", "/drive/v3/files").get("files", [])
    state = {}
    for record in sorted(files, key=lambda f: f["id"]):
        entry = {
            "name": record.get("name"),
            "mimeType": record.get("mimeType"),
            "parents": record.get("parents"),
        }
        if record.get("mimeType") == gws.SHEET_MIME:
            entry["tabs"] = {
                title: gws.read_values(record["id"], title)
                for title in gws.tabs(record["id"])
            }
        state[record["id"]] = entry
    return state


def notion_state(task_dir: Path) -> dict:
    """Every page and database in the task's Notion workspace.

    Scoped by the task's own bearer token, which is what a workspace is on
    mirage's fake -- so this sees the one workspace under test and not the
    three other notion tasks sharing the process.

    Args:
        task_dir (Path): the task directory, for `shared/notion.json`.

    Returns:
        dict: objects keyed by id, with the fields a write would move.
    """
    import notion as client

    token = json.loads(
        (task_dir / "shared" / "notion.json").read_text())["workspace"]
    found = client.call("POST", "/v1/search", {}, token=token)
    state = {}
    for record in sorted(found.get("results", []), key=lambda r: r["id"]):
        state[record["id"]] = {
            "object": record.get("object"),
            "parent": record.get("parent"),
            "archived": record.get("archived"),
            "properties": record.get("properties"),
        }
    return state


def github_state(task_dir: Path) -> dict:
    """Every branch and every tracked path in the task's repositories.

    Scoped to the repositories the task's own `github_allowed_repos`
    names -- the same value the MCP arm is launched with -- so the snapshot
    covers what the arm can reach and nothing else.

    Args:
        task_dir (Path): the task directory.

    Returns:
        dict: branches and their file lists, keyed by `owner/repo`.
    """
    import urllib.error
    import urllib.request

    import mcp_servers

    base = os.environ.get("GITHUB_URL", "http://127.0.0.1:19801").rstrip("/")

    def get(path: str) -> object:
        """One GET against the fake, or None when it refuses."""
        request = urllib.request.Request(f"{base}{path}")
        request.add_header("Authorization", "Bearer fake")
        try:
            with urllib.request.urlopen(request, timeout=30) as reply:
                return json.loads(reply.read() or b"null")
        except (urllib.error.URLError, OSError):
            return None

    # The task names repositories without an owner; the fake knows the
    # owner, so the two are joined here rather than either being restated.
    names = {
        one
        for one in mcp_servers.github_access(task_dir).get(
            "GITHUB_ALLOWED_REPOS", "").split(",") if one
    }
    who = (get("/user") or {}).get("login", "")
    listed = get(f"/users/{who}/repos") or []
    slugs = [
        repo["full_name"] for repo in listed
        if not names or repo.get("name") in names
    ]
    state = {}
    for slug in slugs:
        branches = get(f"/repos/{slug}/branches") or []
        names = sorted(b["name"] for b in branches if isinstance(b, dict))
        state[slug] = {
            branch:
            sorted(entry["path"]
                   for entry in (get(f"/repos/{slug}/git/trees/{branch}"
                                     f"?recursive=1") or {}).get("tree", []))
            for branch in names
        }
    return state


def gcs_state(task_dir: Path) -> dict:
    """Every bucket and object the fake Cloud Storage holds.

    Args:
        task_dir (Path): the task directory; unused, the fake is shared.

    Returns:
        dict: object names and sizes, keyed by bucket.
    """
    import urllib.error
    import urllib.request

    base = os.environ.get("STORAGE_EMULATOR_HOST",
                          "http://127.0.0.1:9070").rstrip("/")

    def get(path: str) -> dict:
        """One GET against the fake, or {} when it refuses."""
        try:
            with urllib.request.urlopen(f"{base}{path}", timeout=30) as reply:
                return json.loads(reply.read() or b"{}")
        except (urllib.error.URLError, OSError):
            return {}

    state = {}
    for bucket in get("/storage/v1/b").get("items", []):
        name = bucket["name"]
        listed = get(f"/storage/v1/b/{name}/o").get("items", [])
        state[name] = {
            item["name"]: item.get("size")
            for item in sorted(listed, key=lambda o: o["name"])
        }
    return state


def snowflake_state(task_dir: Path) -> dict:
    """Every table in the task's one Snowflake database, row for row.

    The database is the fixture Postgres behind `redirect/snowflake`, read
    through the same client the redirect uses, so what is compared is what
    the server on either arm just wrote. Rows are sorted, because a table
    has no order and two identical writes need not leave one.

    Args:
        task_dir (Path): the task directory, which names the database.

    Returns:
        dict: rows keyed by table name.
    """
    import mcp_servers
    import snowflake as snowflake_pg

    database = mcp_servers.snowflake_database(task_dir)
    tables = snowflake_pg.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name", database)
    state = {}
    for row in tables:
        name = row["TABLE_NAME"]
        rows = snowflake_pg.execute(f'SELECT * FROM PUBLIC."{name}"', database)
        state[name] = sorted(
            rows, key=lambda r: json.dumps(r, sort_keys=True, default=str))
    return state


def workspace_state(task_dir: Path) -> dict:
    """The host workspace as a tree, one comparable value.

    The workspace is a fixture like the service backends, and a case that
    writes into it names `workspace` in `mutates` the way one that writes
    rows names `gws`: it is then re-seeded before each arm, the tree the
    two arms start from is compared, and so is the tree each leaves
    behind. A seeder that wrote something different the second time, or a
    re-seed that left the first arm's output in place, shows up here
    rather than as an unexplained disagreement in the replies.

    A tree rather than a flat listing, so a case's `ignore` can name a
    directory -- the pdf-tools server keeps a scratch directory under its
    cwd, which is the MCP arm's business and not a divergence.

    Git's own bookkeeping is left out: a checkout's index and reflog carry
    inode numbers and clock readings by design, so two clones of one
    commit differ there without differing in any file the arm can read.

    Args:
        task_dir (Path): the task directory.

    Returns:
        dict: directories as nested dicts, files as their digest; empty
            when there is no workspace.
    """
    import services

    def tree(directory: Path) -> dict:
        out = {}
        for path in sorted(directory.iterdir()):
            if path.name == ".git":
                continue
            if path.is_dir():
                out[path.name] = tree(path)
            elif path.is_file():
                out[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return out

    root = services.agent_workspace(task_dir)
    return tree(root) if root.is_dir() else {}


# One snapshot per fixture backend a task can mutate. A case names the
# backends it touches; naming none means the case is read-only and no
# snapshot is taken. The workspace is one of them: both arms mount the
# same host directory, so a case that writes a file there has mutated a
# fixture the other arm reads.
STATES = {
    "gws": gws_state,
    "notion": notion_state,
    "github": github_state,
    "gcs": gcs_state,
    "snowflake": snowflake_state,
    "workspace": workspace_state,
}


def state_of(backends: list[str], task_dir: Path) -> dict:
    """Snapshot every named fixture backend.

    Args:
        backends (list[str]): backend names, keys of `STATES`.
        task_dir (Path): the task directory, for per-task scoping.

    Returns:
        dict: the snapshots, keyed by backend.

    Raises:
        SystemExit: a case named a backend with no snapshot function.
    """
    unknown = [name for name in backends if name not in STATES]
    if unknown:
        raise SystemExit(f"parity: no state snapshot for {unknown}; "
                         f"add one to STATES")
    return {name: STATES[name](task_dir) for name in backends}


def resolved(value: object) -> object:
    """Substitute `${VAR}` from the environment, anywhere in a case's args.

    A tool that takes a host path -- `git`'s `repo_path`, the document
    servers' file arguments -- would otherwise need an absolute path
    written into a committed file, which is one machine's answer. The
    mirage side never needs this: its paths are mount paths, which are the
    same everywhere.

    Args:
        value (object): a string, list or dict from a case.

    Returns:
        object: the same shape with variables substituted.

    Raises:
        SystemExit: a case names a variable nothing has set.
    """
    if isinstance(value, str):
        for name in re.findall(r"\$\{([A-Z_][A-Z0-9_]*)\}", value):
            if name not in os.environ:
                raise SystemExit(f"parity: a case names ${{{name}}}, "
                                 f"which is not set")
            value = value.replace(f"${{{name}}}", os.environ[name])
        return value
    if isinstance(value, dict):
        return {key: resolved(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [resolved(item) for item in value]
    return value


async def mcp_reply(session, case: dict) -> str:
    """Call one MCP tool and return its single text reply.

    Args:
        session: an initialised `ClientSession`.
        case (dict): the case, whose `mcp` block names tool and arguments.

    Returns:
        str: the reply text, or the tool's error text.
    """
    spec = case["mcp"]
    result = await session.call_tool(spec["tool"],
                                     resolved(spec.get("args", {})))
    parts = [
        block.text for block in result.content if getattr(block, "text", None)
    ]
    return "\n".join(parts)


async def open_session(stack: AsyncExitStack, name: str, task_dir: Path):
    """Launch one MCP server the way the measured arm launches it.

    Args:
        stack (AsyncExitStack): owns the process and the session.
        name (str): the server name as Toolathlon spells it.
        task_dir (Path): the task directory.

    Returns:
        ClientSession: initialised and ready to call.
    """
    import mcp_servers
    import services
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamablehttp_client

    params = mcp_servers.server_params(name, task_dir,
                                       str(services.agent_workspace(task_dir)))
    if "url" in params:
        read, write, _ = await stack.enter_async_context(
            streamablehttp_client(params["url"]))
    else:
        read, write = await stack.enter_async_context(
            stdio_client(StdioServerParameters(**params)))
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    return session


def mirage_reply(workspace, case: dict) -> str:
    """Run the mirage arm's command line and return what the agent sees.

    `execute` is the whole mirage surface -- the arm's one tool is a shell
    -- so driving it here means the test exercises the same path a run
    would, rather than a library call underneath it.

    Args:
        workspace (Workspace): the arm's workspace.
        case (dict): the case, whose `mirage` block holds `command`.

    Returns:
        str: the command's combined output.
    """
    return workspace.execute(case["mirage"]["command"])


def leaves(group: BaseExceptionGroup) -> list[BaseException]:
    """Every non-group exception inside a possibly nested group.

    Args:
        group (BaseExceptionGroup): the group to flatten.

    Returns:
        list[BaseException]: the leaves, in order.
    """
    found: list[BaseException] = []
    for member in group.exceptions:
        if isinstance(member, BaseExceptionGroup):
            found += leaves(member)
        else:
            found.append(member)
    return found


async def run_case(task: str, task_dir: Path, case: dict, sessions: dict,
                   build, reseed) -> tuple[bool, list[str]]:
    """Run one case down both arms and compare.

    A read-only case runs both arms against the fixture as seeded. A
    mutating one re-seeds before each arm, so the second is not looking at
    the first's writes, and compares the resulting fixture state as well as
    the two replies.

    Args:
        task (str): the task directory name.
        task_dir (Path): the task directory.
        case (dict): the case.
        sessions (dict): initialised MCP sessions, keyed by server name.
        build: callable returning a fresh mirage workspace.
        reseed: coroutine that seeds again and re-enters the services.

    Returns:
        tuple: (passed, complaint lines).
    """
    drop = case.get("ignore", [])
    backends = case.get("mutates", [])
    name = case["mcp"]["server"]
    try:
        if not backends:
            return await compared(task, task_dir, case, sessions[name], build,
                                  reseed, drop, backends)
        # A mutating case re-seeds before each arm, and a re-seed can take
        # the service out from under a server that is already connected to
        # it: `email-paper-homepage` reset the github fake and its MCP
        # server died with "Connection closed" mid-case. So a mutating case
        # gets its own session, opened after its own seed.
        await reseed()
        async with AsyncExitStack() as stack:
            fresh = await open_session(stack, name, task_dir)
            return await compared(task,
                                  task_dir,
                                  case,
                                  fresh,
                                  build,
                                  reseed,
                                  drop,
                                  backends,
                                  seeded=True)
    except ProjectionError as bad:
        return False, [str(bad)]
    except BaseExceptionGroup as group:
        # The mutating path raises inside an `AsyncExitStack` holding the
        # MCP session's task group, and anyio re-raises whatever escapes it
        # wrapped in an ExceptionGroup -- so the plain `except` above never
        # saw it, and one mis-specified case took the whole run down with a
        # traceback instead of failing alone. Anything that is not a
        # projection failure is still someone else's problem.
        found = group.subgroup(ProjectionError)
        if found is None:
            raise
        return False, [str(bad) for bad in leaves(found)]
    except Unseedable as why:
        # The mid-case re-seed can fail for the same reason the first one
        # can. Reported as a failure, not a skip: the task's other cases
        # already ran, so the fixture was reachable a moment ago and
        # something changed underneath the run.
        return False, [f"could not re-seed for this case: {why}"]


async def compared(task: str,
                   task_dir: Path,
                   case: dict,
                   session,
                   build,
                   reseed,
                   drop: list[str],
                   backends: list[str],
                   seeded: bool = False) -> tuple[bool, list[str]]:
    """Run both arms and diff them, with the case already unpacked.

    Args:
        task (str): the task directory name.
        task_dir (Path): the task directory.
        case (dict): the case.
        session: the MCP session for this case's server.
        build: callable returning a fresh mirage workspace.
        reseed: coroutine that seeds again and re-enters the services.
        drop (list[str]): keys to prune before comparing.
        backends (list[str]): fixture backends the case mutates.
        seeded (bool): whether the caller already seeded for the MCP arm.

    Returns:
        tuple: (passed, complaint lines).
    """
    if backends and not seeded:
        await reseed()
    # What each arm starts from, taken after its seed and before its call.
    # "Re-seeded before each arm" is a claim about the workspace as much as
    # about the service, and the workspace is the tree the MCP arm just
    # wrote into.
    mcp_start = workspace_state(task_dir) if backends else None
    # Stripped, because one surface is a tool return and the other is a
    # command's stdout, and a shell's trailing newline is not a divergence.
    mcp_text = projected((await mcp_reply(session, case)).strip(),
                         case["mcp"].get("jq"), case["mcp"].get("raw", False),
                         case["mcp"].get("pipe"))
    mcp_after = state_of(backends, task_dir) if backends else None

    if backends:
        await reseed()
    mirage_start = workspace_state(task_dir) if backends else None
    mirage_text = projected(
        mirage_reply(build(), case).strip(), case["mirage"].get("jq"),
        case["mirage"].get("raw", False), case["mirage"].get("pipe"))
    mirage_after = state_of(backends, task_dir) if backends else None

    if SHOW:
        for arm, text in (("mcp", mcp_text), ("mirage", mirage_text)):
            more = " ..." if len(text) > 240 else ""
            print(f"         {arm:6} {text[:240]!r}{more}")
    problems = difference(pruned(decoded(mcp_text), drop),
                          pruned(decoded(mirage_text), drop))
    problems = [f"reply {line}" for line in problems]
    if backends:
        problems += [
            f"initial {line}" for line in difference(
                pruned(mcp_start, drop), pruned(mirage_start, drop))
        ]
        problems += [
            f"state {line}" for line in difference(pruned(mcp_after, drop),
                                                   pruned(mirage_after, drop))
        ]
    return not problems, problems


def unexpected(case: dict, problems: list[str]) -> list[str]:
    """The comparison lines a `known` case's `expect` patterns do not cover.

    Args:
        case (dict): the case, carrying `expect`.
        problems (list[str]): the lines the comparison produced.

    Returns:
        list[str]: the lines no pattern matches.
    """
    patterns = [re.compile(pattern) for pattern in case["expect"]]
    return [
        line for line in problems
        if not any(pattern.search(line) for pattern in patterns)
    ]


def verdict(case: dict, problems: list[str]) -> str:
    """Classify one case's outcome.

    A case may carry `known`, naming a divergence already understood and
    recorded, and `expect`, one regular expression per line the
    comparison produces for it. Every line has to match one, or the case
    fails like any other: a label that accepted whatever went wrong on its
    case once hid a CLI that could not import, behind a note about
    spreadsheet ids. Known is not a pass -- it stays visible in the output
    and in the summary -- but it does not fail the gate, or a defect that
    cannot be fixed today would make the whole suite useless tomorrow.
    When a known case starts agreeing, the harness says so, so the
    annotation is removed rather than left to rot.

    Args:
        case (dict): the case.
        problems (list[str]): the comparison's lines; empty when the two
            arms agreed.

    Returns:
        str: "ok", "FAIL", "known", or "fixed".
    """
    if case.get("known"):
        if not problems:
            return "fixed"
        return "FAIL" if unexpected(case, problems) else "known"
    return "FAIL" if problems else "ok"


class Tally(NamedTuple):
    """How one task's cases came out."""

    ran: int = 0
    failed: int = 0
    known: int = 0
    fixed: int = 0
    skipped: int = 0
    mismapped: int = 0

    def plus(self, other: "Tally") -> "Tally":
        """Add two tallies.

        Args:
            other (Tally): the tally to add.

        Returns:
            Tally: the sum, field by field.
        """
        return Tally(*(a + b for a, b in zip(self, other)))


async def run_task(task: str, only: list[str] | None) -> Tally:
    """Run every parity case one task declares.

    Args:
        task (str): the task directory name.
        only (list[str] | None): run just these case names, if given.

    Returns:
        Tally: the outcome counts.
    """
    import services

    spec = load(task)
    cases = spec["cases"] if spec else []
    chosen = [case for case in cases if not only or case["name"] in only]
    mapped = {} if only else mapped_clis(task, dataset.local(task))
    if not chosen and not mapped:
        return Tally()

    # One process runs every task here, where a measured run gets a process
    # each -- so what one task exports is the next task's environment.
    # `build_workspace_dir` publishes `AGENT_WORKSPACE`, and `agent_workspace`
    # reads it back before it looks at the task name, so every task after
    # the first was seeded into, and mounted from, the first task's
    # directory. `mirage_env` `setdefault`s `HF_TOKEN` to the task's name,
    # which is the tenant on the Hub fake, so every Hub task after the
    # first read the first task's empty Hub. Each task therefore gets the
    # environment this process had before any task ran, plus its own
    # workspace slot -- assigned rather than defaulted, because a stale
    # export, the previous task's or an operator's, would otherwise
    # decide where this task's fixture lands.
    slot = services.workspaces_dir() / task
    with patch.dict(os.environ, AGENT_WORKSPACE=str(slot)):
        return await run_cases(task, dataset.local(task), chosen, mapped)


def advertised(task: str, server: str, tools: list) -> list:
    """The tools the measured arm advertises, of those a session lists.

    A dataset that hands a task a subset of each server's tools -- Atlas --
    advertises only those, through `mcp_servers.aliasing_server`. A session
    here is the bare server, so the same filter goes on top of it; without
    it, a CLI that lists exactly what the task enables reads as missing
    every tool the task never had.

    Args:
        task (str): the task directory name.
        server (str): the server the tools are from.
        tools (list): the session's `Tool`s.

    Returns:
        list: those the measured arm would advertise.
    """
    picked = getattr(dataset, "enabled_tools", None)
    if picked is None:
        return list(tools)
    import mcp_servers
    enabled = set(picked(task))
    return [
        tool for tool in tools
        if mcp_servers.shown_tool_name(server, tool.name) in enabled
    ]


async def report_coverage(task: str, sessions: dict, cases: list[dict],
                          mapped: dict[str, str]) -> None:
    """Say which advertised operations no case reaches.

    Per server the cases name: the tools it advertises to the model, read
    from the live session rather than a hand-kept table, against the
    tools the task's cases call -- every case the task declares, not only
    the ones `--case` chose. A server the task declares that no case
    names is listed as such rather than started for the count, since some
    need a service the stack was not asked for; the line under-reports,
    never over.

    A server a registered CLI stands in for is counted whether or not a
    case names it, so a CLI no case has ever exercised reads as `0/n`
    rather than going unmentioned.

    Args:
        task (str): the task directory name.
        sessions (dict): open MCP sessions, keyed by server name.
        cases (list[dict]): every case the task declares.
        mapped (dict[str, str]): registered CLI name to the server it
            stands in for.
    """
    named: dict[str, set[str]] = {server: set() for server in mapped.values()}
    for case in cases:
        named.setdefault(case["mcp"]["server"], set()).add(case["mcp"]["tool"])
    for name in sorted(named):
        if name not in sessions:
            continue
        listed = await sessions[name].list_tools()
        shown = sorted(tool.name
                       for tool in advertised(task, name, listed.tools))
        missing = [tool for tool in shown if tool not in named[name]]
        print(f"  cover {name}: {len(shown) - len(missing)}/"
              f"{len(shown)} advertised tool(s) have a case"
              f"{'; none for ' + ', '.join(missing) if missing else ''}")
    silent = [s for s in dataset.needed_mcp_servers(task) if s not in named]
    if silent:
        print(f"  cover no case names {', '.join(silent)}")


# A CLI spells its server's underscores as hyphens, the shell's convention
# for a command name; `browser` is the one not yet named after its server.
ALIASES = {
    "browser": "playwright_with_chunk",
    "gh": "github",
    "hf": "huggingface",
    "kubectl": "k8s",
    "arxiv-local": "arxiv_local",
    "google-calendar": "google_calendar",
    "google-forms": "google_forms",
    "google-map": "google_map",
    "google-sheet": "google_sheet",
    "rail-12306": "rail_12306",
    "web-search": "web_search",
}

# What a CLI built on `cli/toolathlon/tool.mjs` or
# `cli/toolathlon/browser-client.mjs` prints first: its commands are the
# original tool names, so its `--help` can be read against the server's tool
# list.
BANNER = re.compile(r"^(\S+) <command> \['<JSON arguments>'( \| -)?\]$")


def mapped_clis(task: str, task_dir: Path) -> dict[str, str]:
    """Every registered CLI that stands in for one of the task's servers.

    Exact tool transports are checked against the upstream catalog.
    Established CLIs such as gh, hf and kubectl keep their own syntax;
    their result mappings are verified by the task cases.

    Args:
        task (str): the task directory name.
        task_dir (Path): the task directory.

    Returns:
        dict[str, str]: CLI name to server name.
    """
    import yaml

    config = task_dir / "vfs" / "workspace.yaml"
    if not config.is_file():
        return {}
    clis = (yaml.safe_load(config.read_text()) or {}).get("clis") or {}
    servers = set(dataset.needed_mcp_servers(task))
    return {
        name: ALIASES.get(name, name)
        for name in clis if ALIASES.get(name, name) in servers
    }


async def report_mapping(task: str, sessions: dict, mapped: dict[str, str],
                         build) -> int:
    """Check each mapped CLI's commands against its server's tools.

    The schema half of the fidelity question, per CLI: the commands a CLI
    lists are the tools its server advertises, one for one, and each
    command's `--help` is that tool's description and input schema. Read
    off the shell the agent gets and the live session the other arm gets,
    so a CLI whose transport serves a different pin, or drops or renames a
    tool, is a mismatch here before any case has to find it.

    A CLI whose `--help` does not carry the tool-command banner has
    commands of its own and is reported as such, not compared. One whose
    `--help` fails is a mismatch, not a bespoke CLI: a tool-command CLI
    answers `--help` with an error when its transport is down, and that
    error carries no banner either.

    Args:
        task (str): the task directory name.
        sessions (dict): open MCP sessions, keyed by server name.
        mapped (dict[str, str]): CLI name to server name.
        build: callable returning a fresh mirage workspace.

    Returns:
        int: how many CLIs disagree with their server.
    """
    if not mapped:
        return 0
    workspace = build()
    disagreeing = 0
    for cli, server in sorted(mapped.items()):
        if server not in sessions:
            print(f"  map   {cli} -> {server}: FAIL, the server did not "
                  f"start")
            disagreeing += 1
            continue
        listing = workspace.execute_result(f"{cli} --help")
        if listing.get("exit_code"):
            print(f"  map   {cli} -> {server}: FAIL, `{cli} --help` exited "
                  f"{listing['exit_code']}: "
                  f"{(listing.get('stderr') or '').strip()[:200]}")
            disagreeing += 1
            continue
        lines = (listing.get("stdout") or "").strip().splitlines()
        hub_tools = decoded(listing.get("stdout")
                            or "") if cli == "huggingface" else None
        if not isinstance(hub_tools, list) and (not lines
                                                or not BANNER.match(lines[0])):
            print(f"  map   {cli} -> {server}: commands of its own, "
                  f"verified by cases only")
            continue
        tools = {
            tool.name: tool
            for tool in advertised(task, server, (
                await sessions[server].list_tools()).tools)
        }
        # A description can run to several lines, so a listed line is a
        # command only when a tool answers to it or `--help` does. A tool
        # with an empty description is listed as `name:` alone, which the
        # strip above leaves without its space when it is the last line.
        listed = [
            match.group(1)
            for match in (re.match(r"^([A-Za-z0-9_.\-]+):( |$)", line)
                          for line in lines[2:]) if match
        ]
        verbs, shown = [], {}
        if isinstance(hub_tools, list):
            shown = {tool["name"]: tool for tool in hub_tools}
            verbs = list(shown)
        for verb in listed:
            answer = decoded(workspace.execute(f"{cli} {verb} --help").strip())
            if isinstance(answer, dict) and "inputSchema" in answer:
                verbs.append(verb)
                shown[verb] = answer
        problems, matched = [], {}
        for name in sorted(tools):
            # The command is the tool's name (an Atlas CLI's with its
            # underscores hyphens), or the name less the prefix the CLI
            # strips (`woo_`, `canvas_`, `browser_`, `maps_`, `fetch_`,
            # `mcp_howtocook_`, Notion's `API-`) -- and only when no command
            # is the whole name, since `update_cells` is also the tail of
            # `batch_update_cells`. Toolathlon's and Atlas's commands spell
            # underscores as hyphens.
            spelled = name.replace("_", "-")
            found = [v for v in verbs if spelled == v.replace("_", "-")]
            if not found:
                # The longest tail wins: `browser_tab_close` is answered
                # by `tab-close`, not by `close`, which is `browser_close`.
                tails = [
                    v for v in verbs
                    if spelled.endswith("-" + v.replace("_", "-"))
                ]
                longest = max(map(len, tails), default=0)
                found = [v for v in tails if len(v) == longest]
            if len(found) != 1:
                problems.append(
                    f"{name}: {len(found)} command(s) answer to "
                    f"it{': ' + ', '.join(found) if found else ''}")
                continue
            matched[found[0]] = name
        problems += [
            f"{verb}: a command with no tool behind it" for verb in verbs
            if verb not in matched
        ]
        for verb, name in sorted(matched.items()):
            tool = tools[name]
            expected = {
                "description": tool.description,
                "inputSchema": tool.inputSchema
            }
            got = {
                key: shown[verb].get(key)
                for key in ("description", "inputSchema")
            }
            problems += [
                f"{verb} {line}" for line in difference(expected, got)
            ]
        if problems:
            disagreeing += 1
            print(f"  map   {cli} -> {server}: FAIL, {len(matched)}/"
                  f"{len(tools)} tool(s) matched, {len(problems)} "
                  f"disagreement(s):")
            for line in problems[:8]:
                print(f"         {line}")
            if len(problems) > 8:
                print(f"         ... and {len(problems) - 8} more")
        else:
            print(f"  map   {cli} -> {server}: {len(matched)}/{len(tools)} "
                  f"command(s) are the tools, schemas identical")
    return disagreeing


class Services:
    """The dataset's per-run services, re-entered after every seed.

    `arms.open_services` is entered once per run, after the seed and before
    either arm, which is the order the real runner keeps. A mutating case
    seeds again in the middle of a run, and the seeder empties the workspace
    those services were launched in: the emails transport's working
    directory is gone from under it, and every call after that answers
    `[Errno 1] Operation not permitted` from inside its sandbox. So they are
    closed and opened again after each seed, the way the MCP session is.

    Args:
        task_dir (Path): the task directory.
        workdir (str): the run's workspace.
        stack (AsyncExitStack): outlives every re-entry; closes the last.
    """

    def __init__(self, task_dir: Path, workdir: str, stack: AsyncExitStack):
        self.task_dir = task_dir
        self.workdir = workdir
        self.stack = stack
        self.held: AsyncExitStack | None = None

    async def reopen(self) -> None:
        """Close whatever is held and enter the services afresh."""
        import arms

        if self.held is not None:
            await self.held.aclose()
        self.held = await self.stack.enter_async_context(AsyncExitStack())
        arms.open_services(self.task_dir, self.workdir, self.held)


async def run_cases(task: str, task_dir: Path, chosen: list[dict],
                    mapped: dict[str, str]) -> Tally:
    """Run a task's chosen cases, in an environment already made its own.

    Args:
        task (str): the task directory name.
        task_dir (Path): the task directory.
        chosen (list[dict]): the cases to run.
        mapped (dict[str, str]): registered CLI name to the server it
            stands in for; checked before the cases run.

    Returns:
        Tally: the outcome counts.
    """
    import arms
    from workspace import Workspace
    from workspace import config_for as ts_config_for

    # Once, before either arm runs: `AGENT_WORKSPACE` and the fixture
    # addresses are what a case's `${VAR}` resolves against, and the MCP
    # side is called before the first mirage workspace is built.
    workdir = arms.mirage_env(task_dir)
    # A case may need a fixture of its own: a tool that takes a file path
    # reads it out of the workspace, and a case has to put one there.
    os.environ["PARITY_TESTS"] = str(task_dir / "tests")
    print(f"### {task}", flush=True)
    # Named in the log so three runs -- together, alone, reordered -- can
    # be read against each other: this line is the same in all of them
    # exactly when a task's workspace is its own.
    print(f"  workspace: {workdir}", flush=True)
    try:
        seed(task)
    except Unseedable as why:
        print(f"  SKIP  {len(chosen)} case(s): {why}")
        return Tally(skipped=len(chosen))
    closers: list = []

    def build():
        """A workspace built after the current seed, not before it.

        Rebuilt per case rather than reused, because a mutating case
        re-seeds underneath it and a workspace that cached the old listing
        would be reading a fixture that no longer exists.
        """
        workspace = Workspace.create(ts_config_for(task_dir))
        closers.append(workspace.close)
        return workspace

    servers = sorted({case["mcp"]["server"]
                      for case in chosen} | set(mapped.values()))
    failed = known = fixed = 0
    async with AsyncExitStack() as stack:
        # After the seed and before either arm is built, exactly as
        # `arms.build_arm` orders it: a dataset whose fixture is a service
        # built per run has to have it running before a case can call it,
        # and both arms have to reach the same one.
        services = Services(task_dir, workdir, stack)
        await services.reopen()

        async def reseed() -> None:
            """Seed again, then re-enter what the seed took down."""
            seed(task)
            await services.reopen()

        sessions, unstarted = {}, {}
        for name in servers:
            try:
                sessions[name] = await open_session(stack, name, task_dir)
            except Exception as why:  # noqa: BLE001 -- reported per server
                unstarted[name] = f"{type(why).__name__}: {why}"
                print(f"  {name} did not start: {unstarted[name]}")
        spec = load(task)
        await report_coverage(task, sessions, spec["cases"] if spec else [],
                              mapped)
        mismapped = await report_mapping(task, sessions, mapped, build)

        for index, case in enumerate(chosen):
            server = case["mcp"]["server"]
            if server in unstarted:
                passed, problems = False, [unstarted[server]]
            else:
                passed, problems = await run_case(task, task_dir, case,
                                                  sessions, build, reseed)
            # A mutating case re-seeds, and a re-seed restarts the service
            # these shared sessions are connected to -- so every later case
            # was talking down a dead pipe and died with
            # `ClosedResourceError`. It only showed up once a read-only case
            # was written after a mutating one, which is to say the suite
            # was order-dependent without saying so. The mirage side's
            # services are re-entered by `reseed` itself, before the arm
            # that uses them.
            if case.get("mutates") and index < len(chosen) - 1:
                sessions = {
                    name: await open_session(stack, name, task_dir)
                    for name in servers
                }
            mark = verdict(case, problems)
            print(f"  {mark:5} {case['name']}"
                  f"{'  <- ' + case['known'] if mark == 'known' else ''}")
            if mark == "fixed":
                print("         the two arms now agree; drop `known` "
                      "from this case")
            shown = problems
            if mark == "FAIL" and case.get("known"):
                shown = unexpected(case, problems)
                print(f"         not the divergence `known` describes; "
                      f"{len(shown)} line(s) match no `expect` pattern:")
            for line in shown[:8]:
                print(f"         {line}")
            if len(shown) > 8:
                print(f"         ... and {len(shown) - 8} more")
            failed += mark == "FAIL"
            known += mark == "known"
            fixed += mark == "fixed"
    for close in closers:
        close()
    return Tally(len(chosen), failed, known, fixed, mismapped=mismapped)


def tasks_with_cases() -> list[str]:
    """Every task that declares parity cases.

    Returns:
        list[str]: task directory names, sorted.
    """
    return sorted(path.parent.parent.name
                  for path in dataset.local("").glob(f"*/{CASES}"))


def tasks_to_run() -> list[str]:
    """Every task with something to compare: cases, or a mapped CLI.

    Returns:
        list[str]: task directory names, sorted.
    """
    return sorted(
        set(tasks_with_cases()) | {
            task
            for task in dataset.tasks()
            if mapped_clis(task, dataset.local(task))
        })


async def main_async(args) -> int:
    """Run the selected tasks' cases.

    Returns:
        int: 0 when every case passed.
    """
    import services
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env.development")
    # Without this the BigQuery and Cloud Storage cases report themselves
    # skipped on a stack that is pointed at their task and answering,
    # because the endpoints reach this process only through a shell that
    # was told to export them.
    services.load_stack_env()

    chosen = args.tasks or tasks_to_run()
    tally = Tally()
    for task in chosen:
        tally = tally.plus(await run_task(task, args.case))
    print(f"\n{tally.ran} case(s): {tally.ran - tally.failed - tally.known}"
          f" agreed, {tally.failed} failed, {tally.known} known divergence(s)")
    if tally.skipped:
        print(f"{tally.skipped} case(s) SKIPPED -- a service was not pointed "
              f"at their task; they proved nothing, and the gate fails")
    if tally.fixed:
        print(f"{tally.fixed} case(s) marked `known` now agree; drop the "
              f"annotation")
    if tally.mismapped:
        print(f"{tally.mismapped} mapped CLI(s) disagree with their "
              f"server's tools")
    if not args.tasks:
        # The suite-wide gap, on a suite-wide run: what the gate never
        # looked at, said in the same breath as what it passed.
        covered = set(tasks_with_cases())
        every = dataset.tasks()
        without = [name for name in every if name not in covered]
        print(f"{len(without)} of {len(every)} task(s) declare no parity "
              f"cases: {', '.join(without)}")
    return 1 if tally.failed or tally.skipped or tally.mismapped else 0


def main() -> int:
    """Parse arguments and run.

    Returns:
        int: process status.
    """
    parser = argparse.ArgumentParser(
        description="Run one operation down both arms and compare the "
        "answers, for every task that declares parity cases")
    parser.add_argument("tasks", nargs="*", help="task names; default all")
    parser.add_argument("--case",
                        action="append",
                        help="run only these case names")
    parser.add_argument("--list",
                        action="store_true",
                        help="list the tasks that declare cases and stop")
    parser.add_argument("--show",
                        action="store_true",
                        help="print each arm's projected reply per case")
    args = parser.parse_args()
    global SHOW
    SHOW = args.show
    if args.list:
        for task in tasks_to_run():
            spec = load(task)
            mapped = mapped_clis(task, dataset.local(task))
            print(f"{task}: {len(spec['cases']) if spec else 0} case(s), "
                  f"{len(mapped)} mapped CLI(s)")
        return 0
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
