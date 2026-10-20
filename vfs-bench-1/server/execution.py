"""Filesystem confinement for model-directed native processes.

Services and graders stay outside this boundary. The sandbox grants access
only to the run workspace, selected program dependencies and fixture files.
"""
import asyncio
import atexit
import json
import os
import shutil
import signal
import sys
import tempfile
import threading
from contextlib import contextmanager
from functools import cache
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SYSTEM = ('/System', '/usr', '/bin', '/sbin', '/Library', '/private/etc',
          '/private/var/db', '/dev', '/etc', '/opt/homebrew/Cellar',
          '/opt/homebrew/opt', '/opt/homebrew/bin', '/usr/local/Cellar',
          '/lib', '/lib64', '/opt/homebrew/etc/openssl@3/openssl.cnf',
          '/opt/homebrew/etc/ca-certificates/cert.pem')
ENV_KEYS = {
    'MCP_REMOTE_CONFIG_DIR',
    'PUBLIC_SERVICE_URL',
    'YAHOO_CLI_URL',
    'GOOGLE_MAPS_API_KEY',
    'YOUTUBE_API_KEY',
    'WEBSHARE_PROXY_USERNAME',
    'WEBSHARE_PROXY_PASSWORD',
    'MEMORY_FILE_PATH',
    'WOOCOMMERCE_CONSUMER_KEY',
    'WOOCOMMERCE_CONSUMER_SECRET',
    'WORDPRESS_SITE_URL',
    'GITHUB_URL',
    'PATH',
    'LANG',
    'LC_ALL',
    'TZ',
    'PYTHONPATH',
    'UV_PROJECT',
    'ALLOWED_DIR',
    'ALLOWED_COMMANDS',
    'ALLOWED_FLAGS',
    'MAX_COMMAND_LENGTH',
    'COMMAND_TIMEOUT',
    'ALLOW_SHELL_OPERATORS',
    'MAX_OUTPUT_LENGTH',
    'MAX_STDOUT_LENGTH',
    'MAX_STDERR_LENGTH',
    'CLI_PROXY_ENABLED',
    'CLI_PROXY_URL',
    'BASE_URL',
    'OPENAPI_MCP_HEADERS',
    'NODE_OPTIONS',
    'NODE_TLS_REJECT_UNAUTHORIZED',
    'API_URL',
    'GWS_URL',
    'GWS_MOCK_URL',
    'GOOGLE_CLIENT_ID',
    'GOOGLE_CLIENT_SECRET',
    'GOOGLE_REFRESH_TOKEN',
    'XDG_CACHE_HOME',
    'PAPER_API_URL',
    'PAPER_CLI_ENDPOINT',
    'NOTION_URL',
    'NOTION_TOKEN',
    'WEB_FIXTURE',
    'WEB_API_URL',
    'DRIVE_FOLDER_ID',
    'TOKEN_PATH',
    'CREDENTIALS_PATH',
    'SERVICE_ACCOUNT_PATH',
    'GCP_SERVICE_ACCOUNT',
    'GOOGLE_APPLICATION_CREDENTIALS',
    'CALENDAR_OAUTH_PATH',
    'CALENDAR_CREDENTIALS_PATH',
    'CLOUD_LOGGING_API',
    'BIGQUERY_EMULATOR_HOST',
    'STORAGE_EMULATOR_HOST',
    'HF_ENDPOINT',
    'HF_TOKEN',
    'KUBECONFIG',
    'KUBECONFIG_PATH',
    'KUBECTL',
    'KUBECTL_NATIVE',
    'K8S_PROCESS_DIR',
    'HELM_NATIVE',
    'HELM_FIXTURE_URL',
    'HELM_CONFIG_HOME',
    'HELM_CACHE_HOME',
    'HELM_DATA_HOME',
    'PGHOST',
    'PGPORT',
    'PGUSER',
    'PGPASSWORD',
    'PGDATABASE',
    'PG_HOST',
    'PG_PORT',
    'PG_USER',
    'PG_PASSWORD',
    'PG_DATABASE',
    'CANVAS_API_TOKEN',
    'CANVAS_DOMAIN',
    'GITHUB_PERSONAL_ACCESS_TOKEN',
    'GITHUB_ALLOWED_REPOS',
    'GITHUB_READ_ONLY',
    'WOO_API_URL',
    'WOO_CONSUMER_KEY',
    'WOO_CONSUMER_SECRET',
    'WANDB_API_KEY',
    'WANDB_BASE_URL',
    'http_proxy',
    'https_proxy',
    'HTTP_PROXY',
    'HTTPS_PROXY',
    'no_proxy',
    'NO_PROXY',
}
# Model-run code -- the local Python tool and the terminal server's
# commands -- gets what upstream's process has, not what the servers get.
# Upstream hands a service's credentials to that server alone, in the `env`
# block of configs/mcp_servers/<server>.yaml; this runner exports them into
# its own environment for its servers, and a model that printed `os.environ`
# read the store's keys there and fetched the catalogue over REST instead of
# through the WooCommerce server. What passes is the runtime, the airgap's
# proxies, the kubeconfig, what the kubectl and helm wrappers on a
# Kubernetes task's PATH exec and write (server/kubectl.sh, server/helm.sh),
# and the Hub redirect that stands in for the network upstream's Python
# reaches the Hub over. The shared workspace's Python already runs on its
# runtime, kubeconfig and proxies alone (server/shared_workspace.py).
MODEL_ENV_KEYS = {
    'PATH',
    'LANG',
    'LC_ALL',
    'TZ',
    'UV_PROJECT',
    'HF_ENDPOINT',
    'HF_TOKEN',
    'KUBECONFIG',
    'KUBECONFIG_PATH',
    'KUBECTL',
    'KUBECTL_NATIVE',
    'K8S_PROCESS_DIR',
    'HELM_NATIVE',
    'HELM_FIXTURE_URL',
    'HELM_CONFIG_HOME',
    'HELM_CACHE_HOME',
    'HELM_DATA_HOME',
    'http_proxy',
    'https_proxy',
    'HTTP_PROXY',
    'HTTPS_PROXY',
    'no_proxy',
    'NO_PROXY',
}


def model_environment():
    """The part of this process's environment that model-run code sees."""
    return {
        key: value
        for key, value in os.environ.items() if key in MODEL_ENV_KEYS
    }


# The directories the model's Python loads the Hub redirect from.
HUB_REDIRECT = [REPO / 'redirect/hub', REPO / 'redirect/eval_shim']


def hub_python_path():
    """PYTHONPATH for the model's Python, on a task that has the Hub.

    HF_TOKEN is set only for such a task (agent/arms.py `hub_redirect`),
    where HF_ENDPOINT may be set for every task on a stack. The child the
    original handler starts with `uv run` inherits it, so `requests` calls
    to huggingface.co in the model's code reach the fake as huggingface_hub's
    already do (redirect/hub/sitecustomize.py).
    """
    if not os.environ.get('HF_TOKEN'):
        return {}
    return {'PYTHONPATH': os.pathsep.join(str(path) for path in HUB_REDIRECT)}


@contextmanager
def background(handler, port: int = 0, timeout: float = 3):
    """Serve `handler` on a daemon thread, yielding its base URL.

    The join below bounds the serve loop and nothing else, and `shutdown()`
    has already stopped that loop before it is reached, so teardown costs one
    poll interval rather than any wait on a request. The bound is there so a
    serve thread that somehow does not exit cannot wedge a seeder, not
    because a slow handler could: an in-flight request is never waited for by
    either call here.

    That last part is worth spelling out, because it reads like a bug and is
    not. `ThreadingHTTPServer` sets `daemon_threads = True`, so
    `ThreadingMixIn.process_request` marks each request thread a daemon and
    `_Threads.append` drops it instead of tracking it -- which leaves the
    `self._threads.join()` inside `server_close()` joining an empty list.
    Measured on 3.12: 0.2s to tear down with a handler ten seconds into a
    sleep, against 9.7s for the same lifecycle on a server with
    `daemon_threads = False` (the flag `server/sandbox.py` sets for its own
    ThreadingTCPServer for this reason). So do not hand this a server class
    that clears the flag. A handler mid-request is abandoned deliberately,
    because several of these proxy to the live internet.

    Args:
        handler (type): the BaseHTTPRequestHandler subclass to serve.
        port (int): the port to bind, or 0 to let the OS choose.
        timeout (float): seconds to wait for the serve loop to finish.
    """
    server = ThreadingHTTPServer(('127.0.0.1', port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=timeout)


@cache
def runtime_directory(workdir):
    """Keep each run's launcher caches outside its graded filesystem."""
    scratch = tempfile.TemporaryDirectory(prefix='vfs-bench-runtime-')
    atexit.register(scratch.cleanup)
    return Path(scratch.name).resolve()


def environment(values, workdir):
    """Pass fixture settings and runtime controls, never the model/E2B keys."""
    env = {key: str(value) for key, value in values.items() if key in ENV_KEYS}
    # Public API credentials belong to the harness proxy. Original servers
    # require a nonempty key, but commands need only its placeholder.
    for key in ('GOOGLE_MAPS_API_KEY', 'YOUTUBE_API_KEY'):
        if key in env:
            env[key] = 'fixture'
    scratch = runtime_directory(str(Path(workdir).resolve()))
    env.update(TMPDIR=str(scratch),
               UV_CACHE_DIR=str(scratch / 'uv'),
               UV_NO_SYNC='1',
               UV_OFFLINE='1',
               PYTHONDONTWRITEBYTECODE='1',
               GIT_CONFIG_GLOBAL='/dev/null',
               GIT_CONFIG_NOSYSTEM='1')
    return env


def dependencies(paths):
    """Include resolved executable targets and Python's interpreter home."""
    found = set()
    for path in paths:
        path = Path(path).absolute()
        if not path.exists():
            continue
        found.update((path, path.resolve()))
        for parent in (path, *path.parents):
            cfg = parent / 'pyvenv.cfg'
            if cfg.is_file():
                found.add(parent)
                for line in cfg.read_text().splitlines():
                    if line.startswith('home = '):
                        found.add(
                            Path(line.split(' = ', 1)[1]).parent.resolve())
                break
    return found


def prefix(workdir, readable=(), writable=(), *, public_network=False):
    """Fail closed unless the host can enforce the requested boundaries."""
    work = Path(workdir).resolve()
    writes = dependencies([work, *writable])
    reads = dependencies([*SYSTEM, *writes, *readable])
    if sys.platform == 'darwin':

        def outside(paths, listing=()):
            entries = [
                '(require-not (literal ' + json.dumps(str(p)) + '))'
                for p in sorted(listing)
            ]
            entries.extend('(require-not (' +
                           ('subpath' if p.is_dir() else 'literal') + ' ' +
                           json.dumps(str(p)) + '))' for p in sorted(paths))
            return '(require-all ' + ' '.join(entries) + ')'

        # Python discovers namespace packages by listing parent directories.
        # Permit those directory entries, never their ungranted file contents.
        listing = {parent for path in reads for parent in path.parents}
        listing.difference_update(work.parents)

        # Denies take precedence in Seatbelt: express the complement of the
        # permitted paths, rather than combining a blanket deny with allows.
        read_boundary = outside(reads, listing).replace(
            '(require-all ', '(require-all (require-not (literal "/")) ', 1)

        def granted(path):
            return any(path == allowed or (
                allowed.is_dir() and path.is_relative_to(allowed))
                       for allowed in reads)

        # bubblewrap leaves host credentials unmounted. Hide the equivalent
        # standard files on macOS so foreign tools use their explicit env.
        credentials = (Path.home() / '.netrc', Path.home() / '_netrc')
        hidden_metadata = ''.join('(deny file-read-metadata (literal ' +
                                  json.dumps(str(path)) + '))'
                                  for path in credentials if not granted(path))
        profile = (
            '(version 1)(allow default)' + '(deny file-read-data ' +
            read_boundary + ')' + hidden_metadata + '(deny file-write* ' +
            outside(writes | {Path('/dev/null')}) + ')' +
            ('' if public_network else
             '(deny network-outbound (require-not (remote ip "localhost:*")))')
            + '(deny appleevent-send)')
        return ['/usr/bin/sandbox-exec', '-p', profile]
    if sys.platform == 'linux' and not public_network:
        from server.linux_sandbox import executable

        # Keep the host network namespace: fixture clients AND confined
        # servers bound to ephemeral loopback ports must remain reachable.
        # Sandlock performs connect/send on behalf of the child, enforcing
        # destination IPs independently of proxies, DNS and command flags.
        args = [
            executable(), 'run', '--cwd',
            str(work), '--net-allow', '127.0.0.0/8:*', '--net-allow',
            '[::1]:*', '--net-allow', 'icmp://127.0.0.0/8', '--net-allow',
            'icmp://::1', '--net-allow-bind', '*'
        ]
        for path in sorted(reads | {Path('/proc')}):
            args += ['-r', str(path)]
        for path in sorted(writes | {Path('/dev/null')}):
            args += ['-w', str(path)]
        return [*args, '--']
    if sys.platform == 'linux' and shutil.which('bwrap'):
        args = [
            'bwrap', '--die-with-parent', '--unshare-user', '--unshare-pid',
            '--unshare-uts', '--unshare-ipc', '--proc', '/proc', '--dev',
            '/dev'
        ]
        for path in sorted(reads - writes - {Path('/dev')}):
            args += ['--ro-bind', str(path), str(path)]
        for path in sorted(writes):
            args += ['--bind', str(path), str(path)]
        return [*args, '--chdir', str(work), '--']
    raise RuntimeError(
        'Native benchmark execution requires macOS sandbox-exec '
        'or Linux Sandlock (bubblewrap for explicit public-network services); '
        'refusing unrestricted execution')


def launch(params, workdir, readable=(), writable=(), *, public_network=False):
    """Wrap an unchanged foreign command; tool names/schemas stay
    upstream's."""
    env = environment(params.get('env', os.environ), workdir)
    if env.get('XDG_CACHE_HOME') and not any(
            Path(env['XDG_CACHE_HOME']).resolve().is_relative_to(
                Path(root).resolve()) for root in writable):
        env.pop('XDG_CACHE_HOME')
    executable = shutil.which(params['command']) or params['command']
    paths = [executable, *readable]
    # uv reads ancestor manifests while locating a project, even when an
    # explicit project is selected. This grants files, not the repo tree.
    for parent in (REPO, *Path(workdir).resolve().parents):
        paths.extend(parent / name for name in ('pyproject.toml', 'uv.lock',
                                                '.python-version'))
    # These are harness-owned launcher arguments, never the model's argv.
    for arg in params.get('args', []):
        if isinstance(arg, str) and arg.startswith('/') and Path(arg).exists():
            paths.append(arg)
            if Path(arg).is_file() and Path(arg).suffix in {
                    '.py', '.js', '.mjs'
            }:
                paths.append(Path(arg).parent)
    for key, value in env.items():
        if key == 'PATH':
            for name in ('node', 'uv', 'python3', 'python', 'git'):
                if binary := shutil.which(name, path=value):
                    paths.append(binary)
                    if name == 'node':
                        paths.append(Path(binary).resolve().parent.parent)
        elif key == 'PYTHONPATH':
            paths.extend(value.split(os.pathsep))
        elif value.startswith('/') and Path(value).exists():
            # UV's project selection needs its manifests and environment,
            # never tasks/, graders or ground truth in that same checkout.
            if key == 'UV_PROJECT':
                paths.extend(
                    Path(value) / name
                    for name in ('pyproject.toml', 'uv.lock', '.venv'))
            else:
                paths.append(value)
    for path in list(paths):
        candidate = Path(path)
        for parent in candidate.parents:
            paths.extend(parent / name
                         for name in ('pyproject.toml', 'uv.lock',
                                      '.python-version'))
        if (candidate / '.venv').is_dir():
            paths.append(candidate / '.venv')
        if candidate.suffix in {'.js', '.mjs'}:
            for parent in candidate.parents:
                if parent == REPO:
                    break
                if (parent / 'package.json').is_file():
                    paths.append(parent)
    writes = [
        env[key] for key in ('TMPDIR', 'K8S_PROCESS_DIR', 'HELM_CONFIG_HOME',
                             'HELM_CACHE_HOME', 'HELM_DATA_HOME')
        if env.get(key)
    ]
    command = prefix(workdir,
                     paths, [*writes, *writable],
                     public_network=public_network)
    return {
        **params,
        'command': command[0],
        'args': [*command[1:], executable, *params.get('args', [])],
        'env': env,
        'cwd': params.get('cwd', str(workdir)),
    }


# Upstream's own task image, the one scripts/run_single_containerized.sh
# runs every task in (its default `image_name`), pinned by digest. It holds
# upstream's synced Python environment (/workspace/.venv), its npm tree
# (/workspace/node_modules) and its `uv tool` servers, so the model's Python,
# the terminal's commands and the filesystem server run on upstream's Ubuntu,
# GNU tools, interpreters and network rather than on this host.
IMAGE = ('lockon0927/toolathlon-task-image@sha256:'
         '4d04fe4e0a6fdb4946f51bb05120cb44a0eef980231c11252f93b62897afcb9f')
# Where the run script copies upstream's checkout; only the Python tool's
# handler is mounted there, never tasks/ or a grader.
HANDLER = '/workspace/utils/aux_tools/python_interpretor.py'
CONTAINER = None


def container():
    """The upstream task container this run's model tools execute in."""
    return CONTAINER


@contextmanager
def upstream_container(workdir):
    """Run one container of upstream's image for this run's model tools.

    Upstream runs with `--network host` and as root, and so does this. The
    workspace is mounted at its own path, so the services that stay on this
    host and the tools in here read and write the same files under the same
    names; upstream's own path, /workspace/dumps/workspace, would mean two.
    """
    import subprocess
    import uuid
    global CONTAINER
    workdir = str(Path(workdir).resolve())
    handler = (REPO / 'submodule/Toolathlon' /
               'utils/aux_tools/python_interpretor.py')
    if subprocess.run(['docker', 'image', 'inspect', IMAGE],
                      stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode:
        subprocess.run(['docker', 'pull', '--platform', 'linux/amd64', IMAGE],
                       check=True)
    config = json.loads(
        subprocess.check_output([
            'docker', 'image', 'inspect', '--format', '{{json .Config}}', IMAGE
        ]))
    name = '-'.join(
        ('toolathlon-mcp', os.environ.get('COMPOSE_PROJECT_NAME',
                                          'toolathlon'), uuid.uuid4().hex[:8]))
    # The Hub redirect is mounted at its own path, as hub_python_path names it.
    hub = [
        arg for path in HUB_REDIRECT
        for arg in ('--mount',
                    f'type=bind,source={path},target={path},readonly')
    ] if hub_python_path() else []
    ident = subprocess.check_output([
        'docker', 'run', '--detach', '--rm', '--init', '--platform',
        'linux/amd64', '--network', 'host', '--name', name, '--mount',
        f'type=bind,source={workdir},target={workdir}', '--mount',
        f'type=bind,source={handler},target={HANDLER},readonly', *hub,
        '--workdir', workdir, IMAGE, 'sleep', 'infinity'
    ],
                                    text=True).strip()
    env = dict(entry.split('=', 1) for entry in config['Env'])
    previous = CONTAINER
    CONTAINER = {'id': ident, 'image': IMAGE, 'workdir': workdir, 'env': env}
    try:
        yield CONTAINER
    finally:
        hand_back()
        CONTAINER = previous
        subprocess.run(['docker', 'rm', '--force', ident],
                       check=True,
                       stdout=subprocess.DEVNULL)


def hand_back():
    """Give root's files on a Linux bind mount back to this user.

    Upstream grades inside its container, as root. The grader here runs on
    the host, so this comes before grading, and again before cleanup for
    anything written since.
    """
    import subprocess
    if CONTAINER is None or sys.platform != 'linux':
        return
    subprocess.run([
        'docker', 'exec', CONTAINER['id'], 'chown', '-R',
        f'{os.getuid()}:{os.getgid()}', CONTAINER['workdir']
    ],
                   check=False)


def contained(command, env=None, cwd=None):
    """Stdio parameters for a command in the run's upstream container."""
    args = ['exec', '--interactive', '--workdir', cwd or CONTAINER['workdir']]
    for key, value in (env or {}).items():
        args += ['--env', f'{key}={value}']
    return {'command': 'docker', 'args': [*args, CONTAINER['id'], *command]}


async def contained_python_tool(context, parameters):
    """Run the original Python handler in the upstream container.

    Upstream's agent process runs under `uv run main.py`, so the handler
    inherits /workspace/.venv on PATH and as VIRTUAL_ENV, and its own
    `uv run --directory <workspace>` finds /workspace/pyproject.toml by
    walking up from /workspace/dumps/workspace. This workspace is not under
    /workspace, so UV_PROJECT names that project instead. The Hub redirect
    is the one service setting the model's Python gets, as on the host.
    """
    workdir = context.context['_agent_workspace']
    # The first line out is the call's process group: GNU timeout leads one,
    # and everything the handler starts stays in it.
    code = ('import asyncio,importlib.util,json,os,sys;'
            'from types import SimpleNamespace;'
            'print(os.getpgrp(),flush=True);'
            's=importlib.util.spec_from_file_location("original_python",'
            f'{HANDLER!r});'
            'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
            'p=json.load(sys.stdin);'
            'print(json.dumps(asyncio.run(m.on_python_execute_tool_invoke('
            'SimpleNamespace(context=p["context"]),p["parameters"]))))')
    env = {
        'PATH': '/workspace/.venv/bin:' + CONTAINER['env']['PATH'],
        'VIRTUAL_ENV': '/workspace/.venv',
        'UV_PROJECT': '/workspace',
        **{
            key: os.environ[key]
            for key in ('HF_ENDPOINT', 'HF_TOKEN') if key in os.environ
        },
        **hub_python_path(),
    }
    # The handler caps the model's code at 120 seconds; this bounds the
    # handler itself, as the E2B path does.
    params = contained([
        'timeout', '--signal=KILL', '135', '/workspace/.venv/bin/python', '-c',
        code
    ], env, workdir)
    proc = await asyncio.create_subprocess_exec(params['command'],
                                                *params['args'],
                                                stdin=asyncio.subprocess.PIPE,
                                                stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    group = b''
    try:
        # The code goes in only once the group is known, so a call
        # cancelled before then never runs it.
        group = (await proc.stdout.readline()).strip()
        proc.stdin.write(
            json.dumps({
                'context': {
                    '_agent_workspace': workdir
                },
                'parameters': parameters
            }).encode())
        await proc.stdin.drain()
        proc.stdin.close()
        out, err = await proc.communicate()
        if proc.returncode:
            raise RuntimeError(err.decode(errors='replace')[-2000:])
        return json.loads(out)
    finally:
        # As on the host path, kill the whole group, including a command the
        # handler's own timeout left behind or a call the run's wall clock
        # cancelled: stopping the docker client stops neither.
        if proc.returncode is None:
            proc.kill()
        if group.isdigit():
            kill = await asyncio.create_subprocess_exec(
                'docker',
                'exec',
                CONTAINER['id'],
                'bash',
                '-c',
                f'kill -KILL -- -{group.decode()} 2>/dev/null',
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL)
            await kill.wait()
        await proc.wait()


async def python_tool(context, parameters):
    """Run the original Python handler inside the boundary, including file
    writes."""
    if CONTAINER is not None:
        return await contained_python_tool(context, parameters)
    workdir = context.context['_agent_workspace']
    source = (REPO / 'submodule/Toolathlon' /
              'utils/aux_tools/python_interpretor.py')
    code = ('import asyncio,importlib.util,json,sys;'
            'from types import SimpleNamespace;'
            's=importlib.util.spec_from_file_location("original_python",'
            f'{str(source)!r});'
            'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
            'p=json.load(sys.stdin);'
            'print(json.dumps(asyncio.run(m.on_python_execute_tool_invoke('
            'SimpleNamespace(context=p["context"]),p["parameters"]))))')
    params = launch(
        {
            'command': sys.executable,
            'args': ['-c', code],
            'env': {
                **model_environment(), 'UV_PROJECT':
                str(REPO / 'submodule/Toolathlon'),
                **hub_python_path()
            }
        },
        workdir,
        readable=[source, Path(sys.prefix),
                  Path(sys.base_prefix)])
    proc = await asyncio.create_subprocess_exec(params['command'],
                                                *params['args'],
                                                env=params['env'],
                                                cwd=workdir,
                                                stdin=asyncio.subprocess.PIPE,
                                                stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE,
                                                start_new_session=True)
    try:
        out, err = await proc.communicate(
            json.dumps({
                'context': {
                    '_agent_workspace': workdir
                },
                'parameters': parameters
            }).encode())
        if proc.returncode:
            raise RuntimeError(err.decode(errors='replace')[-2000:])
        return json.loads(out)
    finally:
        # Terminate descendants as well as the worker, including a Python
        # command left behind when the upstream handler hits its own timeout.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()


def stop_processes(directory, include_background=True):
    """Kill only groups whose live parent matches the owning daemon record."""
    import subprocess
    for path in Path(directory).glob('*.json'):
        record = json.loads(path.read_text())
        if record['background'] and not include_background:
            continue
        pid = record['pid']
        parent = subprocess.run(
            ['ps', '-p', str(pid), '-o', 'ppid='],
            capture_output=True,
            text=True)
        if parent.stdout.strip() != str(record['parent']):
            continue
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def prepare_project(project):
    """Install the lock before entering the runtime boundary."""
    import subprocess
    project = Path(project)
    if not (project / 'uv.lock').is_file():
        raise RuntimeError(
            f'Native Python project has no dependency lock: {project}')
    subprocess.run(['uv', 'sync', '--locked', '--project',
                    str(project)],
                   check=True)


def prepare(params):
    """Resolve only the harness-owned uv project, before server startup."""
    if Path(params.get('command', '')).name != 'uv':
        return
    args = params.get('args', [])
    for flag in ('--project', '--directory'):
        if flag in args:
            prepare_project(args[args.index(flag) + 1])
            return
    if project := params.get('env', {}).get('UV_PROJECT'):
        prepare_project(project)
