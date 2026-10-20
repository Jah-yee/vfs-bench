import asyncio
import atexit
import hashlib
import json
import math
import os
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from functools import cache
from pathlib import Path

import httpx
from services import agent_workspace, stack_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
# Same override the daemon's own module resolution uses, so the "build it
# first" guard checks the tree the daemon will actually import.
PACKAGES = Path(
    os.environ.get(
        "MIRAGE_PACKAGES",
        REPO_ROOT / "submodule" / "mirage" / "typescript" / "packages"))
DAEMON = PACKAGES / "server" / "dist" / "bin" / "daemon.js"
CORE = PACKAGES / "core" / "dist" / "index.js"


class Daemon:
    """A mirage TypeScript daemon this process started.

    Attributes:
        base (str): its base URL.
        token (str): the bearer every request carries.
        public_network (bool): its builtin HTTP reaches public URLs.
    """

    def __init__(self, base: str, token: str, code_sha: str = "") -> None:
        self.base = base
        self.token = token
        self.code_sha = code_sha
        self.public_network = False

    @property
    def client(self) -> httpx.Client:
        """A client aimed at this daemon.

        Returns:
            httpx.Client: caller closes it.
        """
        return httpx.Client(base_url=self.base,
                            headers={"Authorization": f"Bearer {self.token}"},
                            timeout=600,
                            transport=Patient(httpx.HTTPTransport()))


def retry_after(reply: httpx.Response) -> float:
    """How long a request the daemon turned away should wait.

    Args:
        reply (httpx.Response): the daemon's 429.

    Returns:
        float: its Retry-After, in seconds; one when it gives none.
    """
    try:
        return max(float(reply.headers.get("retry-after", "1")), 0.0)
    except ValueError:
        return 1.0


def patience(request: httpx.Request) -> float:
    """Until when a request the daemon keeps refusing is resent.

    Args:
        request (httpx.Request): as its client sends it.

    Returns:
        float: a `time.monotonic()` deadline, its client's read timeout
            from now; no deadline when the client sets none.
    """
    read = (request.extensions.get("timeout") or {}).get("read")
    return math.inf if read is None else time.monotonic() + read


class Patient(httpx.BaseTransport, httpx.AsyncBaseTransport):
    """Resend a request the daemon's rate limits turned away.

    Mirage's daemon allows each address 1000 requests a minute
    (`@fastify/rate-limit`) and 2000 through its auth hook, both fixed in its
    source, and answers the rest with 429 and a Retry-After before any
    handler runs, so nothing has happened yet. Every tool call is two
    requests, and a model can send over a thousand calls in one reply,
    so hundreds of them would get the daemon's 429 back as their result,
    which the MCP arm has no way to see. So a refused request waits as asked and
    goes again, for as long as its client's read timeout: a daemon that
    keeps refusing past that hands the caller its 429, as before.

    Attributes:
        inner: the transport that sends each attempt.
    """

    def __init__(self, inner) -> None:
        self.inner = inner

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()
        deadline = patience(request)
        while True:
            reply = self.inner.handle_request(request)
            wait = retry_after(reply)
            if reply.status_code != 429 or time.monotonic() + wait > deadline:
                return reply
            reply.read()
            reply.close()
            time.sleep(wait)

    async def handle_async_request(self,
                                   request: httpx.Request) -> httpx.Response:
        await request.aread()
        deadline = patience(request)
        while True:
            reply = await self.inner.handle_async_request(request)
            wait = retry_after(reply)
            if reply.status_code != 429 or time.monotonic() + wait > deadline:
                return reply
            await reply.aread()
            await reply.aclose()
            await asyncio.sleep(wait)

    def close(self) -> None:
        self.inner.close()

    async def aclose(self) -> None:
        await self.inner.aclose()


_RUNNING: Daemon | None = None


def _alive(daemon: Daemon) -> bool:
    """Whether a daemon answers.

    Args:
        daemon (Daemon): the candidate.

    Returns:
        bool: True when it replies to a listing.
    """
    try:
        with httpx.Client(timeout=2) as probe:
            reply = probe.get(
                f"{daemon.base}/v1/workspaces",
                headers={"Authorization": f"Bearer {daemon.token}"})
        return reply.status_code == 200
    except httpx.HTTPError:
        return False


@cache
def code_sha() -> str:
    """Reuse only a daemon that loaded these CLI/VFS/runtime bytes."""
    # The launcher is part of the daemon generation too: changing its
    # environment or authentication boundary must not reuse a process
    # started under the older policy.
    files = [Path(__file__)]
    for directory in ("cli", "cli/toolathlon", "vfs", "server/clients"):
        files.extend((REPO_ROOT / directory).glob("*.mjs"))
    for package in ("core", "node", "server"):
        files.extend((PACKAGES / package / "dist").rglob("*.js"))
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _daemon_env(port: str, token: str, home: Path) -> dict[str, str]:
    """Build the daemon's minimal host environment.

    Workspace configuration is interpolated in ``resolved`` before it is
    posted, so provider credentials do not belong in the daemon process.
    Keeping them out also keeps in-process runtimes from inheriting caller
    secrets.  The bearer is stored in Mirage's mode-0600 token file rather
    than its environment for the same reason.

    `home` is the daemon's own. Mirage keeps its token file and its pid file
    there, and when every daemon shared one, two starting at once could
    each boot reading the other's token.
    """
    token_file = home / "auth_token"
    token_file.write_text(token)
    token_file.chmod(0o600)
    env = {
        key: os.environ[key]
        for key in ("PATH", "TMPDIR", "LANG", "LC_ALL", "TZ")
        if os.environ.get(key)
    }
    env.update({
        "MIRAGE_DAEMON_PORT": port,
        "MIRAGE_AUTH_MODE": "local",
        "MIRAGE_HOME": str(home),
        "SHIM_PYTHON": sys.executable,
    })
    return env


def _free_port() -> str:
    """A loopback port nothing is listening on at the moment of asking.

    Returns:
        str: the port number.
    """
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return str(listener.getsockname()[1])


def _stop(process: subprocess.Popen, home: Path) -> None:
    """Take a daemon down with the process that started it.

    Its home goes too, unless the daemon had already died on its own: then
    the log in it is the only account of why, and it is kept and named.

    Args:
        process (subprocess.Popen): the daemon.
        home (Path): its MIRAGE_HOME.
    """
    crashed = process.poll() not in (None, 0)
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    if crashed:
        print(
            f"mirage daemon exited {process.returncode}; see "
            f"{home / 'daemon.log'}",
            file=sys.stderr)
    else:
        shutil.rmtree(home, ignore_errors=True)


def _spawn(argv: list[str],
           token: str,
           port: str | None = None,
           attempts: int = 1) -> Daemon:
    """Start a daemon owned by this process and wait for it to answer.

    A port picked here is free when it is picked and may not be by the time
    node binds it. A caller whose daemon binds before it does any work can
    ask for more than one attempt, each on a newly picked port.

    Args:
        argv (list[str]): the command.
        token (str): the bearer it enforces.
        port (str | None): the port to bind, or None to pick a free one.
        attempts (int): how many starts to try before giving up.

    Returns:
        Daemon: a live daemon.

    Raises:
        RuntimeError: it exited or never answered; the message carries the
            end of its log.
    """
    root = stack_dir() / "mirage"
    root.mkdir(parents=True, exist_ok=True)
    for _ in range(attempts):
        chosen = port or _free_port()
        running = Daemon(f"http://127.0.0.1:{chosen}", token, code_sha())
        home = Path(tempfile.mkdtemp(prefix="daemon-", dir=root))
        with (home / "daemon.log").open("wb") as log:
            process = subprocess.Popen(argv,
                                       env=_daemon_env(chosen, token, home),
                                       stdout=log,
                                       stderr=subprocess.STDOUT)
        try:
            for _ in range(300):
                if _alive(running):
                    atexit.register(_stop, process, home)
                    return running
                if process.poll() is not None:
                    break
                time.sleep(0.1)
        except BaseException:
            # Interrupted mid-wait, before `_stop` was registered, so
            # nothing else would reap the child or remove its home.
            process.kill()
            process.wait()
            shutil.rmtree(home, ignore_errors=True)
            raise
        detail = (home / "daemon.log").read_text(errors="replace")[-2000:]
        process.kill()
        process.wait()
        shutil.rmtree(home, ignore_errors=True)
    raise RuntimeError(
        f"the mirage daemon did not come up on {running.base}:\n{detail}")


def network_hook(public_network: bool) -> list[str]:
    """Node's arguments for a daemon's builtin HTTP scope.

    `cli/fixture-network.mjs` keeps Mirage's curl and wget on loopback
    fixtures, as the MCP arm's model is kept, unless that model reaches the
    public network itself (arms.public_network).
    """
    return [] if public_network else [
        "--import", str(REPO_ROOT / "cli/fixture-network.mjs")
    ]


def daemon(public_network: bool = False) -> Daemon:
    """This process's daemon, started if it is not up yet.

    One per process rather than one per host. A draw is a process, and a
    daemon serves every workspace it holds from one event loop, behind one
    rate limit and with no crash guard, so draws sharing one would slow
    each other's shell -- the mirage arm's only, since the MCP arm's
    servers are processes of their own. Sharing also meant joining through
    a file on a fixed port, which two draws starting at once raced for, and
    the loser died silently.

    The mirage CLI's own `DaemonClient.ensure_running` is not used, because
    it spawns the *Python* daemon: many task workspaces name `pyodide`,
    which is TypeScript-only, and a Python daemon refuses the config
    outright. This starts the TypeScript one instead.

    `SHIM_PYTHON` is passed at spawn, because it is the one thing
    `cli/shims.mjs` still reads from its own process rather than from a
    workspace's config, and a daemon started from some other shell would
    otherwise spawn the CLIs under the wrong interpreter.

    Args:
        public_network (bool): its builtin HTTP may reach public URLs.

    Returns:
        Daemon: a live daemon.

    Raises:
        RuntimeError: node is missing, the TypeScript packages have not
            been built, or the daemon did not come up.
    """
    global _RUNNING
    if (_RUNNING is not None and _RUNNING.code_sha == code_sha()
            and _RUNNING.public_network == public_network
            and _alive(_RUNNING)):
        return _RUNNING
    if not CORE.is_file() or not DAEMON.is_file():
        raise RuntimeError(f"{DAEMON} missing; build it with\n"
                           "  cd submodule/mirage/typescript && "
                           "pnpm install --config.engine-strict=false && "
                           "pnpm build")
    # A replacement starts beside the daemon it replaces, on a port of its
    # own: workspaces this process made on the old one may still be open,
    # and the old one may still hold the port it was given.
    port = os.environ.get("MIRAGE_DAEMON_PORT") if _RUNNING is None else None
    token = os.environ.get("MIRAGE_AUTH_TOKEN") or secrets.token_urlsafe(32)
    _RUNNING = _spawn(
        ["node", *network_hook(public_network),
         str(DAEMON)],
        token,
        port,
        # It binds before doing anything, so a start lost to a port taken
        # in the meantime is safe to repeat.
        attempts=1 if port else 3)
    _RUNNING.public_network = public_network
    return _RUNNING


def operator_workspace(body: dict,
                       public_network: bool = False) -> tuple[Daemon, str]:
    """Load host-only runtime initialization through Mirage's local API.

    One attempt only: the launcher builds the workspace, runtime
    initialization included, before it binds its port.
    """
    token = secrets.token_urlsafe(32)
    workspace_id = secrets.token_hex(16)
    body = {**body, "workspace_id": workspace_id}
    home = stack_dir() / "operator-workspaces"
    home.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",
                                     suffix=".json",
                                     dir=home,
                                     delete=False) as config:
        json.dump(body, config)
        config_path = Path(config.name)
    try:
        running = _spawn([
            "node", *network_hook(public_network),
            str(REPO_ROOT / "server/clients/workspace_daemon.mjs"),
            str(PACKAGES / "server/dist/index.js"),
            str(config_path)
        ], token)
    except RuntimeError as error:
        raise RuntimeError(
            f"operator-owned Mirage workspace failed to start: {error}"
        ) from None
    finally:
        config_path.unlink(missing_ok=True)
    running.public_network = public_network
    return running, workspace_id


def resolved(config: Path) -> dict:
    """One task's config, in the shape the daemon takes.

    The daemon's create route runs `loadWorkspaceConfig`, not the `...File`
    form, so nothing rebases a relative path for it -- reading the file is
    the client's job, and interpolating `${...}` from this process's
    environment is the point of doing it here. mirage's own CLI prepares a
    body the same way, in `_resolve_config`.

    Not by calling it, though: that function validates the document
    Python-side first, and many task workspaces name `pyodide`, which
    Python refuses as TypeScript-only. So the two halves it composes are
    called directly and the validation is left to the daemon, which is the
    implementation that can actually build the thing.

    Two keys are then the harness's rather than the task's:

    `store` is pinned to ram. The daemon defaults a workspace's state store
    to disk, so that a created workspace survives a restart; for a
    benchmark that is a draw inheriting the previous draw's state, which is
    the failure seeding between arms exists to prevent.

    A `clis.*.config.entry` is made absolute. Only `cli` and `vfs` are
    rebased by mirage's own pass, and `entry` is a path like they are --
    nhl-b2b-analysis's `gsheet` is a program under that task's own `vfs/`.
    Left relative it would resolve against the daemon's cwd.

    Args:
        config (Path): the task's workspace yaml.

    Returns:
        dict: the config to POST.
    """
    from mirage.cli.workspace import _resolve_config_arg
    from mirage.config import _absolutize_scripts

    body = _resolve_config_arg(config)
    _absolutize_scripts(body, config.resolve().parent)
    body.setdefault("store", {"type": "ram"})
    # Environment interpolation produces strings; the email resource and
    # Himalaya CLI require numeric ports in the daemon's JSON configuration.
    email_configs = [
        block.get("config", {}) for block in body.get("mounts", {}).values()
        if block.get("vfs") == "email"
    ] + [
        block.get("config", {}) for block in body.get("clis", {}).values()
        if block.get("cli") == "himalaya"
    ]
    for email_config in email_configs:
        for key in ("imapPort", "smtpPort"):
            if isinstance(email_config.get(key), str):
                email_config[key] = int(email_config[key])
    sys.path.insert(0, str(REPO_ROOT))
    from server.mcp.mcp_servers import timeout_for
    for block in body.get("clis", {}).values():
        deadlines = {
            "BROWSER": "playwright_with_chunk",
            "CALENDAR": "google_calendar",
            "SHEETS": "google_sheet",
            "HELM": "terminal",
            "PDF": "pdf-tools",
            "EXCEL": "excel",
            "WORD": "word",
            "PPTX": "pptx",
        }
        kind = str(block.get("cli", "")).rsplit(":", 1)[-1]
        if kind in deadlines:
            block.setdefault("config",
                             {})["timeoutMs"] = (timeout_for(deadlines[kind]) *
                                                 1000)
        if str(block.get("cli", "")).endswith(":HUB"):
            hub = block.setdefault("config", {})
            if hub["endpoint"] != "https://huggingface.co/mcp":
                hub["endpoint"] = os.environ.get("HF_MCP_URL", hub["endpoint"])
            hub["timeoutMs"] = timeout_for("huggingface") * 1000
    for block in (body.get("clis") or {}).values():
        entry = (block.get("config") or {}).get("entry")
        if isinstance(entry, str) and not Path(entry).is_absolute():
            block["config"]["entry"] = str((config.parent / entry).resolve())
    from services import stack_dir

    from server.execution import launch
    from server.shared_workspace import active
    remote = active()
    if remote:
        body = remote.workspace(body)
    import dataset
    if configure := getattr(dataset, "workspace_config", None):
        configure(body)
    if (dataset.NAME == 'toolathlon'
            and (config.parent.parent / 'task.json').is_file() and 'web_search'
            in dataset.needed_local_tools(config.parent.parent.name)):
        body.setdefault('clis', {})['web-search'] = {
            'cli': str(REPO_ROOT / 'cli/toolathlon/research.mjs') + ':SEARCH',
            'config': {
                'apiBase': os.environ['SEARCH_CLI_URL']
            },
        }
    process_root = stack_dir() / "executions"
    process_root.mkdir(parents=True, exist_ok=True)
    execution_dir = tempfile.mkdtemp(dir=process_root)
    for name, block in (body.get("clis") or {}).items():
        ref = str(block.get("cli", ""))
        config = block.setdefault("config", {})
        if ref.endswith((":KUBECTL", ":HELM", ":MYSQL")):
            config["virtualRoot"] = body.get("profiles",
                                             {}).get("default",
                                                     {}).get("cwd", "/work")
            if remote:
                config.update(launch=remote.ssh,
                              sshCommand=remote.line([config['binary']]),
                              workdir='/work',
                              localWorkdir=str(remote.workdir),
                              env={'PATH': os.environ['PATH']},
                              executionDir=execution_dir)
                continue
            if ref.endswith(":MYSQL"):
                # Only the task's sandbox has the client (server/
                # shared_workspace.py); off it the command refuses to run.
                continue
            env = {
                **os.environ,
                **config.get("env", {}), "KUBECONFIG": config["kubeconfig"],
                "KUBECTL_NATIVE": config.get("native", config["binary"]),
                "K8S_PROCESS_DIR": config.get("processDir", "")
            }
            params = launch(
                {
                    "command": config["binary"],
                    "args": [],
                    "env": env
                }, os.environ["AGENT_WORKSPACE"])
            config.update(launch=[params["command"], *params["args"]],
                          workdir=params["cwd"],
                          env=params["env"],
                          executionDir=execution_dir)
        elif "shims.mjs:" in ref:
            # These processes run fixed CLI programs; still keep per-run
            # transport settings and cancellable process groups explicit.
            config["executionDir"] = execution_dir
    return body


class Workspace:
    """One mirage workspace, held by the daemon.

    Attributes:
        id (str): the daemon's id for it.
    """

    def __init__(self, http: httpx.Client, workspace_id: str) -> None:
        self.http = http
        self.id = workspace_id
        self.process_dirs = set()
        self.overflow_root = '/work'

    @classmethod
    def create(cls, config: Path, public_network: bool = False) -> "Workspace":
        """Build a workspace from a task's yaml.

        Args:
            config (Path): the task's workspace yaml.
            public_network (bool): its curl and wget may reach public URLs.

        Returns:
            Workspace: a handle to the created workspace.

        Raises:
            RuntimeError: the daemon refused the config.
        """
        body = resolved(config)
        host_init = any(
            isinstance(entry, dict)
            and "initModule" in entry.get("config", {})
            for entry in body.get("runtimes", []))
        if host_init:
            running, workspace_id = operator_workspace(body, public_network)
            http = running.client
        else:
            running = daemon(public_network)
            http = running.client
            reply = http.post("/v1/workspaces", json={"config": body})
            if reply.status_code != 201:
                http.close()
                raise RuntimeError(
                    f"workspace create failed: {reply.text[:600]}")
            workspace_id = reply.json()["id"]
        workspace = cls(http, workspace_id)
        home = (body.get('env') or {}).get('HOME')
        if isinstance(home, str) and home in body.get('mounts', {}):
            workspace.overflow_root = home
        workspace.process_dirs = {
            block.get("config", {}).get("executionDir")
            for block in body.get("clis", {}).values()
        } - {None}
        return workspace

    async def execute_async(self,
                            command: str,
                            stdin: bytes | None = None,
                            cwd: str | None = None) -> str:
        result = await self.execute_result_async(command, stdin, cwd)
        out, err = result.get("stdout", ""), result.get("stderr", "")
        return f"{out}\n{err}" if out and err else out or err

    async def execute_result_async(self,
                                   command: str,
                                   stdin: bytes | None = None,
                                   cwd: str | None = None) -> dict:
        """Wait for a cancellable daemon job, including its cleanup on
        abort."""
        async with httpx.AsyncClient(base_url=self.http.base_url,
                                     headers=self.http.headers,
                                     timeout=650,
                                     transport=Patient(
                                         httpx.AsyncHTTPTransport())) as http:
            body = {"command": command}
            if cwd is not None:
                body["cwd"] = cwd
            # Even if cancellation arrives during submission,
            # recover the job ID
            # before cleaning up. Otherwise the server could keep
            # an orphan job.
            endpoint = f"/v1/workspaces/{self.id}/shell?background=true"
            if stdin is None:
                request = http.post(endpoint, json=body)
            else:
                request = http.post(endpoint,
                                    files={
                                        "request":
                                        ("request.json", json.dumps(body),
                                         "application/json"),
                                        "stdin": ("stdin.bin", stdin,
                                                  "application/octet-stream"),
                                    })
            submit = asyncio.create_task(request)
            job = None
            try:
                reply = await asyncio.shield(submit)
                reply.raise_for_status()
                job = reply.json()["job_id"]
                while True:
                    reply = await http.post(f"/v1/jobs/{job}/wait",
                                            json={"timeout_s": 30})
                    reply.raise_for_status()
                    detail = reply.json()
                    if detail["status"] in {"done", "failed", "canceled"}:
                        break
                if detail["status"] != "done":
                    raise RuntimeError(detail.get("error") or detail["status"])
                return detail["result"]
            except BaseException as error:
                if isinstance(error, asyncio.CancelledError):
                    from server.execution import stop_processes
                    for directory in self.process_dirs:
                        stop_processes(directory, include_background=False)

                async def stop():
                    response = await submit
                    response.raise_for_status()
                    job_id = job or response.json()["job_id"]
                    response = await http.delete(f"/v1/jobs/{job_id}")
                    response.raise_for_status()
                    response = await http.post(f"/v1/jobs/{job_id}/wait",
                                               json={})
                    response.raise_for_status()

                await asyncio.shield(stop())
                raise

    def execute(self, command: str) -> str:
        """Synchronous entry point for CLI callers."""
        result = self.execute_result(command)
        out, err = result.get("stdout", ""), result.get("stderr", "")
        return f"{out}\n{err}" if out and err else out or err

    def execute_result(self, command: str) -> dict:
        """The daemon's whole reply, exit code included, for a caller that
        has to tell a command that failed from one that printed nothing."""
        reply = self.http.post(f"/v1/workspaces/{self.id}/shell",
                               json={"command": command})
        reply.raise_for_status()
        return reply.json()

    async def save_overflow(self, text: str) -> str:
        """Save output in the actual mount, including RAM workspaces."""
        import shortuuid
        from services import overflow_notice

        identifier = shortuuid.uuid()
        directory = f"{self.overflow_root}/.overlong_tool_outputs"
        path = f"{directory}/{identifier}.json"
        # Payload bytes travel on stdin, never in command text. A task may
        # mount its home at /workspace rather than the default /work.
        await self.execute_async(f"mkdir -p {shlex.quote(directory)}")
        await self.execute_async(f"cat > {shlex.quote(path)}",
                                 text.encode("utf-8"))
        return overflow_notice(text, identifier, path)

    def close(self) -> None:
        """Drop the workspace, ignoring one the daemon has already lost."""
        from server.execution import stop_processes
        for directory in self.process_dirs:
            stop_processes(directory)
        try:
            self.http.delete(f"/v1/workspaces/{self.id}")
        except httpx.HTTPError:
            pass
        finally:
            self.http.close()


def config_for(task_dir: Path) -> Path:
    """The yaml a task's workspace is built from.

    Kept as a function rather than inlined: the seam is where a second
    backend would go.

    Args:
        task_dir (Path): the task directory.

    Returns:
        Path: the config to create the workspace from.
    """
    return task_dir / "vfs" / "workspace.yaml"


def main() -> int:
    """Smoke-test the backend: create a workspace, run the given commands.

    Returns:
        int: process exit status.
    """
    task_dir = Path(sys.argv[1]).resolve()
    os.environ.setdefault("AGENT_WORKSPACE", str(agent_workspace(task_dir)))
    ws = Workspace.create(config_for(task_dir))
    try:
        for command in sys.argv[2:]:
            print(f"$ {command}")
            print(ws.execute(command)[:600])
    finally:
        ws.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
