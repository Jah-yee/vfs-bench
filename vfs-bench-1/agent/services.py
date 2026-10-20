import fcntl
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Toolathlon's own cap, same name and default as upstream: it applies this
# to MCP results (custom_mcp_util.py) and to function-tool results
# (custom_run_impl.py) alike, so every tool in either arm gets one rule.
MAX_TOOL_OUTPUT = int(os.getenv("BENCH_MAX_SINGLE_TURN_RETURN_CHARS", 100000))

# Different checkouts may set TMPDIR to different locations. Their fixture
# ports and Docker project are still shared by the host, so the locks need
# one stable path regardless of that environment variable.
LOCKS = Path("/tmp/toolathlon-locks")
# The one lock every runner took before draws held their own. A checkout
# still on that code takes it exclusively and then resets every fake, so a
# draw holds it shared: draws on this code overlap each other, and never
# one on the old code.
LEGACY_LOCK = Path("/tmp/toolathlon-fixture-services.lock")


def _flock(path: Path, mode: int, what: str):
    """Open one lock file and take it, saying so if that has to wait.

    Args:
        path (Path): the lock file.
        mode (int): `fcntl.LOCK_EX` or `fcntl.LOCK_SH`.
        what (str): what is being waited for, for the message.

    Returns:
        the open file, which holds the lock until it is closed.
    """
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), mode | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"waiting for {what}", flush=True)
        fcntl.flock(handle.fileno(), mode)
    return handle


@contextmanager
def holding(names):
    """Hold what one draw shares with others, for setup, model and grading.

    One advisory host lock per resource rather than one for the host: a
    stack fake, a host port a task's own service binds, the task itself.
    Two draws wait for each other only where they would touch the same one,
    so a draw whose services are all its own runs beside any other. Taken
    in sorted order, so two draws each wanting what the other holds cannot
    deadlock, and released by the kernel if a runner dies.

    Args:
        names: the resources, as names that are safe in a file name.

    Yields:
        None: once every one of them is held.
    """
    LOCKS.mkdir(parents=True, exist_ok=True)
    handles = [
        _flock(LEGACY_LOCK, fcntl.LOCK_SH,
               "a runner on older code to release the fixture services")
    ]
    try:
        for name in sorted(set(names)):
            handles.append(_flock(LOCKS / f"{name}.lock", fcntl.LOCK_EX, name))
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


def stack_dir() -> Path:
    """Where the fixture stack keeps what it hands the host.

    `bin/start.sh` writes three things here that no arm could work out for
    itself: the generated service-account key, the launch time a BigQuery
    fixture was built at, and the endpoints the stack actually bound. The
    container sees the same directory as `/fixtures`.

    Returns:
        Path: an absolute path, which may not exist yet.
    """
    return Path(os.environ.get("STACK_DIR",
                               REPO_ROOT / "state" / "stack")).resolve()


def load_stack_env(override: bool = False) -> None:
    """Adopt the per-task variables `server/fakes/gcp.py` generated.

    They cannot be defaults in `.env.development` the way the always-on
    ports are, because they do not exist until a task names a BigQuery
    fixture: the endpoint, the key path, and above all `BQ_LAUNCH_TIME`,
    which is a fresh clock reading per task and is what the evaluator uses
    to find the answer table. Reading the file means a run is correct
    whether or not somebody remembered to `eval "$(bin/start.sh env)"`
    after the stack was pointed at this task -- and a shell that did
    still wins, because dotenv does not overwrite what is already set.

    Args:
        override (bool): replace values already in the environment. False
            everywhere but after a seed, where the file has just been
            rewritten and is the newer of the two -- the launch time it
            carries belongs to the fixture that seed built, not to the one
            the environment still remembers.
    """
    # The stack's own addresses, derived from the ports rather than read
    # from anywhere. They were written per task, which made
    # four constants look like per-task state -- and left the consumers
    # carrying defaults that disagreed with it: `mcp_servers.py` fell back
    # to the raw emulator on 9050 where the stack publishes the proxy on
    # 9051. `setdefault`, so a shell that exported them still wins.
    proxy = f"http://127.0.0.1:{os.environ.get('BQ_PROXY_PORT', '9051')}"
    for name, value in (
        ("BIGQUERY_EMULATOR_HOST", proxy),
        ("BQ_ENDPOINT", proxy),
        ("STORAGE_EMULATOR_HOST",
         f"http://127.0.0.1:{os.environ.get('GCS_PORT', '9070')}"),
        ("GCP_SERVICE_ACCOUNT",
         str(stack_dir() / "gcp-service_account.keys.json")),
    ):
        os.environ.setdefault(name, value)

    # And what the emulator was launched with, out of its own record, which
    # only `gcp.point_at` writes.
    fixture = stack_dir() / "fixture.json"
    if not fixture.is_file():
        return
    loaded = json.loads(fixture.read_text(encoding="utf-8"))
    published = {}
    if loaded.get("seeded_at"):
        published["BQ_LAUNCH_TIME"] = loaded["seeded_at"]
    if loaded.get("bigquery"):
        published["BQ_PROJECT"] = loaded["bigquery"]["project"]
    for name, value in published.items():
        if override or name not in os.environ:
            os.environ[name] = value


def workspaces_dir() -> Path:
    """Where every run's scratch directory lives.

    Returns:
        Path: an absolute path, which may not exist yet.
    """
    return (REPO_ROOT / "state" / "workspaces").resolve()


def seeded_workspace(task: str) -> Path | None:
    """The workspace the last seed filled, if it was this task's.

    What a grader run by hand grades. A run names its workspace after
    itself, so there is no fixed directory to point at -- but there is no
    need to guess either: every seed writes down which one it filled and
    when, beside it (`seed_record`). The last seed is the record carrying
    the newest time, ranked by that time rather than by anything a search
    would use, because every such search is wrong in a case somebody
    would actually hit. Newest-by-name ranks a hand-run seed below a
    measured run from last week, since only one of the two carries a
    timestamp; mtime ranks by whatever last wrote a file into it.

    `run_agent` never calls this: it knows the answer, having chosen it.

    That time has one-second resolution, so two seeds started in the same
    second tie on it. The record's own modification time breaks the tie,
    which unlike a workspace's is written by the seed and by nothing after
    it, and its name breaks any tie left, so the answer never depends on the
    order a directory happens to be listed in.

    Answering None when the last seed was a *different* task's is the point
    rather than a limitation: grading a task that is not the one currently
    seeded would score it against another task's live services.

    Args:
        task (str): the task name.

    Returns:
        Path | None: the directory, or None if the last seed was not this
            task's, or nothing has been seeded at all.
    """
    records = [(json.loads(path.read_text(encoding="utf-8")),
                path.stat().st_mtime_ns, path.name)
               for path in workspaces_dir().glob("*.seed.json")]
    if not records:
        return None
    loaded, _, _ = max(records,
                       key=lambda found:
                       (found[0].get("seeded_at") or "", found[1], found[2]))
    if loaded.get("task") != task or not loaded.get("workspace"):
        return None
    found = Path(loaded["workspace"])
    return found if found.is_dir() else None


def agent_workspace(task_dir: Path) -> Path:
    """Where this run's scratch directory lives.

    Under `state/`, and deliberately not inside the task directory. It was
    `<task_dir>/agent_workspace` until it became clear what that made the
    parent directory: upstream's `python_execute` is an unsandboxed host
    subprocess with the workspace as its cwd, and 28 of the 46 tasks
    declare it, so `ls ..` handed one arm the task's own `README.md`, its
    `dumps/` and its upstream checkout. The mirage arm is confined to the
    VFS root and could reach none of it -- and a difference between the
    arms that is not the tool surface is the one thing being measured
    cannot survive.

    One chain, because every caller has to agree on the answer: the arm
    writes here, the MCP servers are given it as their cwd and their
    allowed root, and the evaluator is pointed at it afterwards. A caller
    that resolved it differently would grade a directory the arm never
    touched -- an empty tree, scored as a total failure with no error.

    `AGENT_WORKSPACE` is the override, and it is how a measured run gets a
    directory named after itself: `run_agent` exports
    `state/workspaces/<run_id>/` before it seeds, so the seeder fills that
    one, the arm writes in it, the grader reads it, and it is still there
    afterwards paired with `dumps/<run_id>.json`. It is also what lets the
    workspace be a bind mount shared with a container, since the path has
    to read the same on both sides of that boundary.

    Without it -- a seed run by hand -- the answer is the bare task name,
    which is the scratch slot rather than a record of anything.

    Args:
        task_dir (Path): the task directory.

    Returns:
        Path: an absolute path, which may not exist yet.
    """
    return Path(
        os.environ.get("AGENT_WORKSPACE")
        or workspaces_dir() / task_dir.name).resolve()


def empty_workspace(task_dir: Path) -> Path:
    """Empty this run's workspace in place, making it if it is missing.

    In place rather than removed and made again, because the directory is
    also the run's claim on its id: `run_agent` takes an id by creating the
    directory, and while it was gone an identical draw started in the same
    second could take the same id and seed into the same directory.

    Args:
        task_dir (Path): the task directory.

    Returns:
        Path: the emptied workspace.
    """
    workspace = agent_workspace(task_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    for entry in workspace.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)
    return workspace


def seed_record(task_dir: Path) -> Path:
    """Where a seed writes down what it did: the task, the workspace it
    filled, and the time its fixtures came into existence.

    Beside the workspace, not inside it, where the arm could list it; and
    one per workspace rather than one per stack. That time reaches both
    arms' system prompts and the evaluator's `--launch-time`, so a single
    record shared by every draw on the host would hand a draw that seeded
    first the clock of whichever seeded after it.

    Args:
        task_dir (Path): the task directory.

    Returns:
        Path: an absolute path, which may not exist yet.
    """
    workspace = agent_workspace(task_dir)
    return workspace.parent / f"{workspace.name}.seed.json"


def ground_truth(task: str) -> Path:
    """Where a seeder writes the answer sheet it just generated.

    Upstream's evaluators take a `--groundtruth_workspace`: a directory of
    files saying what a correct end state looks like, which the evaluator
    reads and the agent never sees. Most of upstream's are committed once
    and describe a static fixture. A few of ours cannot be, because the
    seeder invents the fixture -- `sla-timeout-monitor` generates fifteen
    tickets against the current clock, so which of them is overdue is only
    known to the pass that made them, and upstream's committed copy
    describes the day upstream last ran its own preprocess.

    Under `state/` rather than in the task directory, for the reason
    `agent_workspace` is: a file listing which answers are correct has no
    business inside the tree the graded arm runs next to. Here rather than
    in either caller, because the seeder writes it and the grader reads it
    and a path spelled twice is a path that drifts.

    Args:
        task (str): the task name.

    Returns:
        Path: an absolute path, which may not exist yet.
    """
    return (REPO_ROOT / "state" / "groundtruth" / task).resolve()


def yf_dsn() -> str:
    """Resolve the fixture database both yahoo-finance surfaces read.

    Returns:
        str: a libpq connection string.
    """
    port = os.environ.get("PG_PORT", "5433")
    return os.environ.get(
        "YF_DSN", f"postgresql://eigent:camel@localhost:{port}/vfs_bench")


def howtocook_home() -> Path:
    """Where server/mcp/setup_howtocook.py puts the pinned package.

    Returns:
        Path: the installed package root, holding both the built server and
            the recipe corpus.
    """
    return (REPO_ROOT / "vendor" / "howtocook-mcp" / "node_modules" /
            "howtocook-mcp").resolve()


def howtocook_corpus() -> Path:
    """The recipe file both howtocook surfaces read.

    The MCP server reads it because its own `data/recipes.js` does; the
    mirage arm reads it because `cli/cook_cli.py` is pointed
    here. One file, so the two arms cannot drift.

    Returns:
        Path: all_recipes.json inside the pinned package.
    """
    return howtocook_home() / "all_recipes.json"


def web_fixture(task_dir: Path) -> Path:
    """The captured web responses both fetch surfaces read.

    Args:
        task_dir (Path): the task directory.

    Returns:
        Path: the task's shared/web_fixture.json.

    Raises:
        FileNotFoundError: the task has not been captured.
    """
    path = task_dir / "shared" / "web_fixture.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"no web capture at {path}; run `uv run python "
            f"task/toolathlon/script/capture_web.py --task {task_dir.name}`")
    return path.resolve()


def logging_api(task: str) -> str:
    """The per-task Cloud Logging endpoint on the fixture API server.

    One URL both arms and the evaluator agree on. The task segment is the
    namespace: each task's entries live under their own store directory on
    the server side, so an arm can never read another task's log.

    Args:
        task (str): the task name.

    Returns:
        str: the base URL the logging clients call.
    """
    base = os.environ.get("API_URL", "http://127.0.0.1:9110").rstrip("/")
    return f"{base}/api/{task}/logging"


def overlong_note(text: str, workdir: str) -> str:
    """Truncate `text`, save the whole of it, and describe where it went.

    Mirrors Toolathlon's _truncate_overlong_tool_output: the cap alone would
    lose the bytes, and the local-*_overlong_* tools search the saved file.

    Args:
        text (str): the full tool output.
        workdir (str): the agent workspace holding .overlong_tool_outputs.

    Returns:
        str: the truncated output with a pointer to the saved file.
    """
    import shortuuid

    save_dir = Path(workdir).resolve() / ".overlong_tool_outputs"
    save_dir.mkdir(parents=True, exist_ok=True)
    short_uuid = shortuuid.uuid()
    path = save_dir / f"{short_uuid}.json"
    path.write_text(text, encoding="utf-8")
    from server.shared_workspace import active
    if remote := active():
        remote.save(f'.overlong_tool_outputs/{short_uuid}.json', text)
        path = Path('/work/.overlong_tool_outputs') / path.name
    return overflow_notice(text, short_uuid, str(path))


def overflow_notice(text: str, short_uuid: str, path: str) -> str:
    """Describe the same cap for disk and virtual overflow files."""
    return (text[:MAX_TOOL_OUTPUT] +
            f" ...\n\n(The output of the tool call (shortuuid identifier: "
            f"{short_uuid}) is too long! Only the first {MAX_TOOL_OUTPUT} "
            f"characters are shown here. The original output length is "
            f"{len(text)} characters. The full output has been saved to the "
            f"file {path}. Please check this file carefully, as it may be "
            f"very long!)")
