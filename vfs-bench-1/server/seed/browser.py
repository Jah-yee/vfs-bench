"""Original browsers run locally, or beside a task's E2B Kubernetes cluster."""
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from server.mcp.setup_browser import (PACKAGE, VENDOR, arguments, image_name,
                                      options)
from server.seed.final_batch import TASKS as FINAL_TASKS
from server.shared_workspace import run

REPO = Path(__file__).resolve().parents[2]
TASKS = {
    'shopping-helper', 'nvidia-stock-analysis', 'academic-pdf-report',
    'add-bibtex', 'cvpr-research', 'profile-update-online', 'hk-top-conf',
    'gdp-cr5-analysis', 'llm-training-dataset',
    'inter-final-performance-analysis', *FINAL_TASKS
}
CURRENT = None


def active():
    return CURRENT


def local_params(workdir):
    """Original stdio server in the run's local browser container."""
    if not CURRENT:
        raise RuntimeError('Local browser session is not running')
    return {
        'command':
        'docker',
        'args': [
            'exec', '-i', CURRENT['container_id'], 'node',
            '/opt/browser/vendor/browser-mcp/node_modules/' + PACKAGE +
            '/cli.js', *arguments(workdir), '--no-sandbox'
        ],
        'env': {
            'PATH': os.environ['PATH']
        }
    }


def install(box):
    """Install the original lock and its corresponding Chromium binary."""
    for name in ('package.json', 'package-lock.json'):
        box.files.write('/opt/browser/vendor/browser-mcp/' + name,
                        (REPO / 'vendor/browser-mcp' / name).read_bytes(),
                        user='root')
    for name in ('server/clients/browser.mjs',
                 'cli/toolathlon/browser-client.mjs'):
        box.files.write('/opt/browser/' + name, (REPO / name).read_bytes(),
                        user='root')
    run(box, 'cd /opt/browser/vendor/browser-mcp && '
        'npm ci --ignore-scripts --no-audit --no-fund && '
        'PLAYWRIGHT_BROWSERS_PATH=/opt/browser/browsers '
        'node node_modules/playwright/cli.js install --with-deps chromium',
        timeout=600)
    # The terminal uses upstream's lock and the original fork's Python sources.
    source = REPO / 'submodule/toolathlon_gym/local_servers/cli-mcp-server'
    for path in (source / 'src').rglob('*.py'):
        box.files.write('/opt/terminal/' +
                        str(path.relative_to(source / 'src')),
                        path.read_bytes(),
                        user='root')


def preview_source(box):
    """Clone the captured branch through the original repository URL."""
    folder = REPO / 'task/toolathlon/k8s-pr-preview-testing/shared/fixtures'
    source = json.loads((folder / 'source.json').read_text())
    bundle = (folder / 'repository.bundle').read_bytes()
    if hashlib.sha256(
            bundle).hexdigest() != source['sha256']['repository.bundle']:
        raise ValueError('Original preview repository checksum mismatch')
    box.files.write('/opt/preview-source.bundle', bundle, user='root')
    import shlex
    run(
        box, 'git clone --bare --branch ' + shlex.quote(source['branch']) +
        ' /opt/preview-source.bundle /opt/preview-source.git')
    actual = run(
        box, 'git --git-dir=/opt/preview-source.git rev-parse ' +
        shlex.quote(source['branch'])).stdout.strip()
    if actual != source['revision']:
        raise ValueError(
            'Original preview branch revision differs from capture')
    run(box,
        'git config --system --add safe.directory /opt/preview-source.git')
    for url in (source['url'], source['url'].removesuffix('.git')):
        run(
            box, 'git config --system --add '
            'url.file:///opt/preview-source.git.insteadOf ' + shlex.quote(url))
    return source


@contextmanager
def connect(remote, virtual_root='/work'):
    """One worker per arm; the original MCP process uses its own context."""
    from server.mcp.mcp_servers import timeout_for
    box = remote.box
    previous = os.environ.get('BROWSER_URL')
    directory = '/home/user/.browser'
    run(box, 'install -d -o user -g user -m 700 ' + directory)
    box.files.write(directory + '/options.json',
                    json.dumps(options('/work')),
                    user='user')
    remote.browser_record = {
        'sandbox_id':
        box.sandbox_id,
        'package':
        PACKAGE,
        'options':
        options('/work'),
        'network':
        'live',
        'filesystem':
        'ssh' if remote.shared_disk else 's3-fuse',
        'browser_lock_sha256':
        hashlib.sha256(
            (REPO /
             'vendor/browser-mcp/package-lock.json').read_bytes()).hexdigest(),
        'workspace': {
            key: remote.config[key]
            for key in ('bucket', 'region', 'key_prefix')
        },
    }
    remote.env['PLAYWRIGHT_BROWSERS_PATH'] = '/opt/browser/browsers'
    handle = box.commands.run(
        'cd /work && exec node /opt/browser/server/clients/browser.mjs ' +
        directory + '/options.json ' + directory + '/endpoint 127.0.0.1 0 ' +
        virtual_root,
        user='user',
        envs=remote.env,
        background=True,
        timeout=0)
    try:
        for attempt in range(120):
            probe = box.commands.run('cat ' + directory +
                                     '/endpoint 2>/dev/null || true',
                                     user='user',
                                     timeout=10)
            if probe.stdout.startswith('http://127.0.0.1:'):
                native_api = probe.stdout.strip()
                break
            if attempt == 119:
                raise RuntimeError('Original browser worker did not start')
            time.sleep(.25)
        remote.env['BROWSER_URL'] = native_api
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        remote_port = int(native_api.rsplit(':', 1)[1])
        subprocess.run([
            *remote.ssh[:-1], '-O', 'forward', '-L',
            f'127.0.0.1:{port}:127.0.0.1:{remote_port}', remote.ssh[-1]
        ],
                       check=True,
                       capture_output=True)
        os.environ['BROWSER_URL'] = f'http://127.0.0.1:{port}'
        box.files.write(
            '/opt/browser/cli/toolathlon/browser-native.mjs',
            '#!/usr/bin/env node\n'
            'import {runBrowser} from "./browser-client.mjs";\n'
            'const r=await runBrowser(process.argv.slice(2),' +
            json.dumps(native_api) + ',' +
            str(timeout_for('playwright_with_chunk') * 1000) + ');\n'
            'process.stdout.write(r.stdout);process.stderr.write(r.stderr);'
            'process.exitCode=r.exitCode;\n',
            user='root')
        run(
            box, 'chmod 755 /opt/browser/cli/toolathlon/browser-native.mjs && '
            'ln -sfn /opt/browser/cli/toolathlon/browser-native.mjs '
            '/usr/local/bin/browser')
        yield
    finally:
        handle.kill()
        if previous is None:
            os.environ.pop('BROWSER_URL', None)
        else:
            os.environ['BROWSER_URL'] = previous


@contextmanager
def serve(task, workdir):
    """Own a local container; mount only this arm's workspace and settings."""
    global CURRENT
    if task not in TASKS:
        raise ValueError(f'No browser task setup for {task}')
    from task.toolathlon import shell_cwd
    virtual_root = shell_cwd(task) or '/work'
    previous, old_url = CURRENT, os.environ.get('BROWSER_URL')
    workdir = Path(workdir).resolve()
    image = image_name()
    subprocess.run(['docker', 'image', 'inspect', image],
                   check=True,
                   stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory(prefix='browser-') as directory:
        directory = Path(directory).resolve()
        settings = options(workdir)
        # Upstream utils/mcp/tool_servers.py applies this for root. The
        # browser container, like upstream's Docker environment, runs as root.
        settings['sandbox'] = False
        (directory / 'options.json').write_text(json.dumps(settings))
        container = subprocess.check_output([
            'docker', 'run', '--detach', '--rm', '--init', '--publish',
            '127.0.0.1::3000', '--mount',
            f'type=bind,source={workdir},target={workdir}', '--mount',
            f'type=bind,source={directory},target={directory}', '--workdir',
            str(workdir), image, 'node',
            '/opt/browser/server/clients/browser.mjs',
            str(directory / 'options.json'),
            str(directory / 'endpoint'), '0.0.0.0', '3000', virtual_root
        ],
                                            text=True).strip()
        try:
            for _ in range(120):
                if (directory / 'endpoint').is_file():
                    break
                time.sleep(.1)
            else:
                log = subprocess.check_output(['docker', 'logs', container],
                                              stderr=subprocess.STDOUT,
                                              text=True)
                raise RuntimeError('Local browser worker did not start: ' +
                                   log[-2000:])
            port = subprocess.check_output(
                ['docker', 'port', container, '3000/tcp'], text=True).strip()
            os.environ['BROWSER_URL'] = 'http://' + port
            CURRENT = {
                'hosting':
                'local-docker',
                'container_id':
                container,
                'image_id':
                subprocess.check_output(
                    ['docker', 'inspect', '--format', '{{.Image}}', container],
                    text=True).strip(),
                'package':
                PACKAGE,
                'options':
                settings,
                'network':
                'live',
                'filesystem':
                'disk',
                'browser_lock_sha256':
                hashlib.sha256(
                    (VENDOR / 'package-lock.json').read_bytes()).hexdigest()
            }
            yield CURRENT
        finally:
            subprocess.run(['docker', 'rm', '--force', container],
                           check=True,
                           stdout=subprocess.DEVNULL)
            CURRENT = previous
            if old_url is None:
                os.environ.pop('BROWSER_URL', None)
            else:
                os.environ['BROWSER_URL'] = old_url


def grade(task, workdir, launch_time, timeout):
    """Run untouched original grading sources with the locked local browser."""
    import io
    import tarfile

    import yaml

    from server.seed.kubernetes import UPSTREAM, original
    prefix = f'tasks/finalpool/{task}'
    with tempfile.TemporaryDirectory(prefix='tb-grade-',
                                     dir='/tmp') as directory:
        directory = Path(directory)
        archive = subprocess.check_output([
            'git', '-C',
            str(UPSTREAM), 'archive', 'HEAD', prefix + '/evaluation', 'utils'
        ])
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(directory, filter='data')
        configs = directory / 'configs/mcp_servers'
        configs.mkdir(parents=True)
        for target, source in (('token_key_session.py',
                                'token_key_session_example.py'),
                               ('global_configs.py',
                                'global_configs_example.py')):
            (configs.parent / target).write_bytes(original('configs/' +
                                                           source))
        config = yaml.safe_load(
            original('configs/mcp_servers/playwright_with_chunk.yaml'))
        config['params'] = local_params(workdir)
        (configs / 'playwright_with_chunk.yaml').write_text(
            yaml.safe_dump(config))
        (directory / 'res_log.json').write_text('{}')
        result = subprocess.run([
            'uv', 'run', '-m',
            prefix.replace('/', '.') + '.evaluation.main', '--agent_workspace',
            str(workdir), '--res_log_file',
            str(directory / 'res_log.json'), '--launch_time', launch_time or ''
        ],
                                cwd=directory,
                                env={
                                    **os.environ, 'UV_PROJECT': str(UPSTREAM),
                                    'UV_NO_SYNC': '1'
                                },
                                timeout=timeout)
        return result.returncode
