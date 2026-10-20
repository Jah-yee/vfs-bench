"""Per-arm state for the remaining original Toolathlon research tasks."""
import hashlib
import io
import json
import os
import selectors
import subprocess
import tarfile
import tempfile
from contextlib import ExitStack, contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

from server.seed.business import restore_environment
from server.seed.kubernetes import UPSTREAM, original
from server.seed.papers import close

REPO = Path(__file__).resolve().parents[2]
TASKS = (
    'meeting-assign',
    'notion-movies',
    'nvidia-market',
    'vlm-history-completer',
    'notion-find-job',
    'search-ca-school',
    'subway-planning',
    'trip-adviser',
    'trip-itinerary-generator',
    'upenn-campus-route',
    'identify-all-songs',
    'youtube-repo',
    'train-ticket-plan',
    'fillout-online-forms',
)
CURRENT = None


def active():
    return CURRENT


def credentials(task):
    from task.toolathlon import needed_mcp_servers
    servers = needed_mcp_servers(task)
    required = [
        key for name, key in [(
            'google_map', 'GOOGLE_MAPS_API_KEY'), ('youtube',
                                                   'YOUTUBE_API_KEY')]
        if name in servers and not os.environ.get(key)
    ]
    if task == 'fillout-online-forms':
        path = Path(
            os.environ.get('GOOGLE_APPLICATION_CREDENTIALS',
                           UPSTREAM / 'configs/google_credentials.json'))
        try:
            value = json.loads(path.read_text())
        except (OSError, ValueError):
            value = {}
        if not all(
                value.get(key) and value[key] not in ('fake', 'fixture', 'XX')
                for key in ('client_id', 'client_secret', 'refresh_token')):
            required.append('benchmark Google OAuth credentials '
                            '(GOOGLE_APPLICATION_CREDENTIALS)')
    if required:
        raise RuntimeError(task + ' requires ' + ', '.join(required))


@contextmanager
def notion(task, stack):
    from server.clients import notion as client
    folder = REPO / 'task/toolathlon' / task / 'shared'
    config = json.loads((folder / 'notion.json').read_text())
    integ = REPO / 'submodule/mirage/integ'
    process = subprocess.Popen([
        str(integ / 'node_modules/.bin/tsx'),
        str(REPO / 'server/fakes/notion_api.mjs'), '--fixture', task,
        '--fixture-root',
        str(folder / 'fixtures/rendered')
    ],
                               cwd=integ,
                               stdout=subprocess.PIPE,
                               text=True)
    stack.callback(close, process)
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        if not selector.select(timeout=45):
            raise RuntimeError('Notion fixture did not start')
        line = process.stdout.readline().strip()
    if not line.startswith('NOTION_URL=http://127.0.0.1:'):
        raise RuntimeError('Notion fixture startup failed: ' + line)
    os.environ.update(NOTION_URL=line.split('=', 1)[1], NOTION_TOKEN=task)
    client.reset(task, task)
    yield config


@contextmanager
def serve(task, workdir):
    global CURRENT
    from server.seed.travel_video import serve as tools
    credentials(task)
    previous = CURRENT
    keys = ('NOTION_URL', 'NOTION_TOKEN', 'BUSINESS_EMAIL_CONFIG',
            'BUSINESS_IMAP_PORT', 'BUSINESS_SMTP_PORT', 'BUSINESS_TASK',
            'HF_ENDPOINT', 'HF_TOKEN', 'PUBLIC_SERVICE_URL', 'GITHUB_URL')
    saved = {key: os.environ.get(key) for key in keys}
    with ExitStack() as stack:
        stack.callback(restore_environment, saved)
        directory = Path(
            stack.enter_context(
                tempfile.TemporaryDirectory(prefix='final-tasks-',
                                            dir=REPO / 'state/research')))
        from server.seed.research_sheets import source_tree
        taskdir, digest = source_tree(task, directory)
        from server.seed.public_services import serve as public_services
        api, requests = stack.enter_context(
            public_services(railway=task == 'train-ticket-plan'))
        os.environ.update(PUBLIC_SERVICE_URL=api,
                          GITHUB_URL=api,
                          HF_ENDPOINT='https://huggingface.co',
                          HF_TOKEN=os.environ.get('HF_TOKEN', ''))
        record = {
            'public_api_requests': requests,
            'task': task,
            'source_tree_sha256': digest,
            'directory': str(directory)
        }
        if task in ('notion-movies', 'notion-find-job'):
            record['notion'] = stack.enter_context(notion(task, stack))
            (taskdir / 'files/duplicated_page_id.txt').write_text(
                record['notion']['page_id'])
            (directory / 'redirect/sitecustomize.py').write_bytes(
                (REPO / 'redirect/eval_shim/notion_redirect.py').read_bytes())
        if task == 'meeting-assign':
            archive = original(
                'tasks/finalpool/meeting-assign/files/files.tar.gz')
            site = directory / 'site'
            site.mkdir()
            with tarfile.open(fileobj=io.BytesIO(archive)) as source:
                source.extractall(site, filter='data')
            from server.execution import background
            handler = partial(SimpleHTTPRequestHandler, directory=str(site))
            stack.enter_context(background(handler, port=30137))
            record['site_sha256'] = hashlib.sha256(archive).hexdigest()
        if task in ('meeting-assign', 'notion-find-job'):
            os.environ['BUSINESS_TASK'] = task
            from server.seed.final_mail import serve as mail
            record['mail'] = stack.enter_context(mail(task, directory))
            with (directory / 'redirect/sitecustomize.py').open('a') as shim:
                shim.write(
                    (REPO / 'redirect/eval_shim/mail_redirect.py').read_text())
        if task == 'fillout-online-forms':
            credential_path = Path(
                os.environ.get('GOOGLE_APPLICATION_CREDENTIALS',
                               UPSTREAM / 'configs/google_credentials.json'))
            (directory / 'configs/google_credentials.json').write_bytes(
                credential_path.read_bytes())
            (directory / 'redirect/sitecustomize.py').write_text('')
            result = subprocess.run([
                str(UPSTREAM / '.venv/bin/python'), '-m',
                f'tasks.finalpool.{task}.preprocess.main', '--agent_workspace',
                str(workdir), '--launch_time',
                os.environ.get('TASK_LAUNCH_TIME', '')
            ],
                                    cwd=directory,
                                    capture_output=True,
                                    text=True,
                                    timeout=180)
            if result.returncode:
                raise RuntimeError('Original Forms preprocessing failed: ' +
                                   result.stderr)
        record['tools'] = stack.enter_context(tools(task, workdir))
        if task == 'nvidia-market':
            redirect = directory / 'redirect'
            (redirect / 'sitecustomize.py').write_bytes(
                (REPO /
                 'redirect/yahoo_capture/sitecustomize.py').read_bytes())
            (redirect / 'capture.py').write_bytes(
                (REPO / 'redirect/yahoo_capture/capture.py').read_bytes())
        CURRENT = record
        try:
            yield record
        finally:
            CURRENT = previous


def browser_ready(task):
    if task != 'meeting-assign':
        return
    from server.seed.browser import active as browser

    # localhost in the browser container reaches the exact same archived site.
    program = (
        "require('net').createServer(s=>{const t=require('net').connect(30137,"
        "'host.docker.internal');s.pipe(t);t.pipe(s);"
        "s.on('error',()=>t.destroy());"
        "t.on('error',()=>s.destroy());}).listen(30137,'127.0.0.1')")
    subprocess.run([
        'docker', 'exec', '-d',
        browser()['container_id'], 'node', '-e', program
    ],
                   check=True)


def grade(task, workdir, launch_time, timeout):
    import yaml

    from server.mcp.mcp_servers import (TIMEOUT_CONFIG, server_params,
                                        upstream_config)
    from task.toolathlon import local, needed_mcp_servers
    if not CURRENT or CURRENT['task'] != task:
        raise RuntimeError(
            'Grade requires this task’s active isolated services')
    directory = Path(CURRENT['directory'])
    configs = directory / 'configs/mcp_servers'
    configs.mkdir(parents=True, exist_ok=True)
    for name in needed_mcp_servers(task):
        config_name = TIMEOUT_CONFIG.get(name, name)
        config = yaml.safe_load(upstream_config(config_name))
        config['params'] = server_params(name, local(task), str(workdir))
        (configs / (config_name + '.yaml')).write_text(yaml.safe_dump(config))
    # Only the railway grader consumes this log, for the launch timestamp.
    record = {'config': {'launch_time': launch_time}}
    (directory / 'res_log.json').write_text(json.dumps(record))
    args = [
        '--agent_workspace',
        str(workdir), '--res_log_file',
        str(directory / 'res_log.json')
    ]
    taskdir = directory / 'tasks/finalpool' / task
    evaluator = (taskdir / 'evaluation/main.py').read_text()
    if '--launch_time' in evaluator:
        args += ['--launch_time', launch_time]
    truth = taskdir / 'groundtruth_workspace'
    if '--groundtruth_workspace' in evaluator:
        # Toolathlon always supplies this argument.  Its task config resolves
        # a missing directory to None, which the shell command renders as the
        # literal string "None".
        args += [
            '--groundtruth_workspace',
            str(truth) if truth.exists() else 'None'
        ]
    result = subprocess.run([
        str(UPSTREAM / '.venv/bin/python'), '-m',
        f'tasks.finalpool.{task}.evaluation.main', *args
    ],
                            cwd=directory,
                            env={
                                **os.environ, 'PYTHONPATH':
                                str(directory / 'redirect')
                            },
                            timeout=timeout)
    return result.returncode
