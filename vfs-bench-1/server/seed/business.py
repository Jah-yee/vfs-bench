"""Original SQL-backed Canvas/WooCommerce fixtures in owned E2B sandboxes."""
import hashlib
import io
import json
import os
import shlex
import shutil
import socket
import tarfile
import tomllib
from contextlib import ExitStack, contextmanager
from pathlib import Path

import requests
from e2b import Sandbox
from e2b.sandbox.commands.command_handle import CommandExitException

from server.kubernetes_template import receipt
from server.sandbox import Tunnel, sandbox
from server.seed import (business_bigquery, business_forms, business_mail,
                         business_mcp, business_sheets, canvas_fixture,
                         woocommerce_fixture)
from server.seed.kubernetes import command, original, original_paths

REPO = Path(__file__).resolve().parents[2]
TASKS = {
    'inventory-sync': 'woocommerce',
    'woocommerce-update-cover': 'woocommerce',
    'filter-low-selling-products': 'woocommerce',
    'woocommerce-new-product': 'woocommerce',
    'canvas-art-quiz': 'canvas',
    'canvas-art-manager': 'canvas',
    'canvas-new-students-notification': 'canvas',
    'canvas-homework-grader-python': 'canvas',
    'canvas-arrange-exam': 'canvas',
    'canvas-do-quiz': 'canvas',
    'canvas-submit-late-work': 'canvas',
    'woocommerce-stock-alert': 'woocommerce',
    'update-material-inventory': 'woocommerce',
    'woocommerce-new-welcome': 'woocommerce',
    'woocommerce-customer-survey': 'woocommerce',
    'woocommerce-product-recall': 'woocommerce'
}


def tokens(task):
    """Read task identity from its own committed token configuration."""
    from addict import Dict
    path = ('other_key.py'
            if task == 'canvas-art-quiz' else 'token_key_session.py')
    namespace = {
        '__file__':
        str(REPO / 'submodule/Toolathlon/tasks/finalpool' / task / path)
    }
    exec(compile(original(f'tasks/finalpool/{task}/{path}'), path, 'exec'),
         namespace)
    return Dict(namespace['all_token_key_session'])


def setup_args(service, task):
    if service == 'canvas':
        return 'start'
    identity = tokens(task)
    users = json.loads(original('configs/users_data.json'))['users']
    for index, user in enumerate(users, start=1):
        if user['woocommerce_consumer_key'] == identity.woocommerce_api_key:
            if (user['woocommerce_consumer_secret']
                    != identity.woocommerce_api_secret
                    or not identity.woocommerce_site_url.rstrip('/').endswith(
                        '/store' + str(user['id']))):
                raise ValueError(
                    'Task WooCommerce identity differs from users_data')
            # Select this task's store using the original one-based user slice.
            return f'start {index} 1'
    raise ValueError(
        'Task WooCommerce account missing from original users_data')


def transfer_in(box, workdir):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:gz') as archive:
        archive.add(workdir, arcname='.')
    box.files.write('/tmp/workspace.tar.gz', data.getvalue(), user='root')
    command(
        box, 'sudo mkdir -p /work && sudo find /work -mindepth 1 -delete && '
        'sudo tar -xzf /tmp/workspace.tar.gz -C /work && '
        'sudo chown -R user:user /work')


def transfer_out(box, workdir):
    command(
        box, 'sudo tar -czf /tmp/workspace.tar.gz -C /work . && '
        'sudo chmod 644 /tmp/workspace.tar.gz')
    data = box.files.read('/tmp/workspace.tar.gz', format='bytes')
    root = Path(workdir)
    for path in root.iterdir():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        archive.extractall(root, filter='data')


def bootstrap(box, service, task):
    prefixes = [
        f'tasks/finalpool/{task}', f'deployment/{service}', 'deployment/utils',
        'utils'
    ]
    paths = sorted({p for prefix in prefixes for p in original_paths(prefix)})
    paths += ['configs/users_data.json', 'uv.lock']
    hashes = {}
    files = {}
    for path in paths:
        data = original(path)
        files[path] = data
        hashes[path] = hashlib.sha256(data).hexdigest()
    for name in ['global_configs', 'token_key_session']:
        data = original(f'configs/{name}_example.py')
        files[f'configs/{name}.py'] = data
        hashes[f'configs/{name}_example.py'] = hashlib.sha256(data).hexdigest()
    # Transfer the exact original bytes together instead of making one E2B
    # request per file. Hashes still name each original source independently.
    bundle = io.BytesIO()
    with tarfile.open(fileobj=bundle, mode='w:gz') as archive:
        for path, data in files.items():
            entry = tarfile.TarInfo(path)
            entry.size = len(data)
            entry.mode = 0o644
            archive.addfile(entry, io.BytesIO(data))
    box.files.write('/tmp/original-toolathlon.tar.gz',
                    bundle.getvalue(),
                    user='root')
    command(
        box, 'sudo mkdir -p /opt/toolathlon && '
        'sudo tar -xzf /tmp/original-toolathlon.tar.gz -C /opt/toolathlon')
    # The native setup uses uv as a launcher; install only its required
    # libraries, at versions from the original lock. Do not resolve latest.
    lock = tomllib.loads(original('uv.lock').decode())
    required = {
        'requests', 'aiohttp', 'addict', 'pyyaml', 'pandas', 'numpy',
        'openpyxl', 'python-dotenv', 'beautifulsoup4', 'tenacity', 'tqdm',
        'sympy', 'termcolor', 'openai-agents', 'pillow', 'requests-oauthlib'
    }
    if task in ('woocommerce-stock-alert',
                'update-material-inventory') or task in business_forms.TASKS:
        required.update(
            {'google-api-python-client', 'google-auth-oauthlib', 'gspread'})
    if task == 'woocommerce-new-welcome':
        # The token stub needs cryptography, and the fixture API that is
        # Cloud Logging fastapi and uvicorn; see `business_bigquery.start`.
        required.update(
            {'google-cloud-bigquery', 'cryptography', 'fastapi', 'uvicorn'})
    packages = {p['name']: p for p in lock['package']}
    pending = list(required)
    while pending:
        for dep in packages[pending.pop()].get('dependencies', []):
            if dep['name'] not in required:
                required.add(dep['name'])
                pending.append(dep['name'])
    pins = [
        packages[name]['name'] + '==' + packages[name]['version']
        for name in sorted(required)
    ]
    if {p.split('==')[0] for p in pins} != required:
        raise ValueError('Original lock does not cover fixture dependencies')
    command(
        box,
        'sudo python3 -m pip install --break-system-packages -q uv==0.8.22 ' +
        ' '.join(map(shlex.quote, pins)),
        timeout=180)
    command(
        box, 'sudo chmod +x /opt/toolathlon/deployment/' + service +
        '/scripts/*.sh')
    box.commands.run('sudo dockerd > /tmp/dockerd.log 2>&1',
                     background=True,
                     timeout=0)
    command(
        box,
        'for i in $(seq 1 30); do sudo docker info >/dev/null 2>&1 && exit 0; '
        'sleep 1; done; cat /tmp/dockerd.log; exit 1')
    sources = json.loads((REPO / 'server/business-sources.json').read_text())
    if hashes[f'deployment/{service}/scripts/setup.sh'] != sources[
            'setup_sha256'][service]:
        raise ValueError('Service setup changed since dependency capture')
    for image in sources['images'][service]:
        command(box,
                'sudo docker pull ' + shlex.quote(image['pinned']) +
                ' && sudo docker tag ' + shlex.quote(image['pinned']) + ' ' +
                shlex.quote(image['source']),
                timeout=300)
    if service == 'woocommerce':
        artifact = sources['wp_cli']
        response = requests.get(artifact['url'], timeout=90)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != artifact['sha256']:
            raise ValueError('WP-CLI capture checksum mismatch')
        box.files.write(
            '/opt/toolathlon/deployment/woocommerce/cache/wp-cli.phar',
            response.content,
            user='root')
    args = setup_args(service, task)
    print(f'Initializing original {service} containers...', flush=True)
    result = command(box,
                     'cd /opt/toolathlon && sudo -E bash deployment/' +
                     service + '/scripts/setup.sh ' + args,
                     timeout=1000)
    return hashes, result


def expose(box, remote_port, local_port, channel, stack):
    # TLS (where the original service uses it) remains inside this byte tunnel.
    assets = json.loads(
        (REPO / 'server/kubernetes-binaries.json').read_text())['websocat']
    result = box.commands.run('test -x /tmp/websocat && echo ready || true',
                              timeout=10)
    if not result.stdout.strip():
        command(
            box, 'curl -fsSL ' + shlex.quote(assets['url']) +
            ' -o /tmp/websocat && '
            'printf %s ' +
            shlex.quote(assets['sha256'] + '  /tmp/websocat\n') +
            ' | sha256sum -c - && chmod 755 /tmp/websocat')
    box.commands.run(
        f'/tmp/websocat -b --exit-on-eof ws-l:0.0.0.0:{channel} '
        f'tcp:127.0.0.1:{remote_port}',
        background=True,
        timeout=0)
    tunnel = Tunnel(f'wss://{box.get_host(channel)}', port=local_port)
    stack.callback(tunnel.close)
    return tunnel.port


@contextmanager
def serve(task, workdir):
    service = TASKS[task]
    ports = [10001, 20001] if service == 'canvas' else [10003]
    has_mail = 'emails' in json.loads(
        original(
            f'tasks/finalpool/{task}/task_config.json'))['needed_mcp_servers']
    # Never reuse an existing local service, which could contain another run.
    for port in ports:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', port))
    template = receipt()
    keys = [
        'BUSINESS_SOURCE_RECORD', 'BUSINESS_SANDBOX_ID', 'BUSINESS_TASK',
        'CANVAS_API_TOKEN', 'CANVAS_DOMAIN', 'CANVAS_API_BASE',
        'WORDPRESS_SITE_URL', 'WOOCOMMERCE_CONSUMER_KEY',
        'WOOCOMMERCE_CONSUMER_SECRET', 'WOOCOMMERCE_API_BASE',
        'BUSINESS_EMAIL_CONFIG', 'BUSINESS_IMAP_PORT', 'BUSINESS_SMTP_PORT',
        'GWS_URL', 'DRIVE_FOLDER_ID', 'BQ_ENDPOINT', 'BQ_PROJECT',
        'BIGQUERY_EMULATOR_HOST', 'GCP_SERVICE_ACCOUNT',
        'STORAGE_EMULATOR_HOST', 'API_URL', 'FORMS_CLI_URL'
    ]
    previous = {key: os.environ.get(key) for key in keys}
    with sandbox(template['template_id'], {
            'task': task,
            'service': service
    }) as box, ExitStack() as stack:
        stack.callback(restore_environment, previous)
        # Claim the owned sandbox before starting any dependent service.  The
        # exact-handler email CLI uses this identity to select the tunneled
        # BUSINESS_EMAIL_CONFIG that business_mail.start publishes below.
        os.environ.update(BUSINESS_SANDBOX_ID=box.sandbox_id,
                          BUSINESS_TASK=task)
        print(f'e2b {service} sandbox={box.sandbox_id}', flush=True)
        hashes, setup = bootstrap(box, service, task)
        evidence = REPO / 'state/business'
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / f'{box.sandbox_id}-setup.log').write_text(setup.stdout +
                                                              setup.stderr)
        remote_mcp = {}
        if task in {
                'canvas-new-students-notification', 'canvas-art-manager',
                'canvas-homework-grader-python', 'canvas-arrange-exam',
                'canvas-do-quiz', 'canvas-submit-late-work'
        }:
            remote_mcp['canvas'] = business_mcp.prepare(box, 'canvas')
            if has_mail:
                remote_mcp['emails'] = business_mcp.prepare(box, 'emails')
        mail = business_mail.start(box, task, stack) if has_mail else None
        sheets = (business_sheets.start(box, task, stack)
                  if task in ('woocommerce-stock-alert',
                              'update-material-inventory') else None)
        bigquery = (business_bigquery.start(box, stack)
                    if task == 'woocommerce-new-welcome' else None)
        forms = business_forms.start(
            box, task, stack) if task in business_forms.TASKS else None
        transfer_in(box, workdir)
        captured = None
        if service == 'woocommerce' and woocommerce_fixture.folder(
                task).is_dir():
            print(f'Restoring original {task} capture...', flush=True)
            captured = woocommerce_fixture.restore(box, task, hashes)
        elif service == 'canvas' and canvas_fixture.folder(task).is_dir():
            print(f'Restoring original {task} capture...', flush=True)
            captured = canvas_fixture.restore(box, task, hashes, remote_mcp)
        else:
            print(f'Seeding original {task}...', flush=True)
            try:
                seeded = command(
                    box,
                    'cd /opt/toolathlon && sudo -E ' +
                    (business_sheets.REDIRECT if sheets or forms else
                     business_bigquery.REDIRECT if bigquery else '') +
                    'uv run -m tasks.finalpool.' + task +
                    '.preprocess.main --agent_workspace /work',
                    timeout=600)
            except CommandExitException as error:
                (evidence /
                 f'{box.sandbox_id}-seed.log').write_text(error.stdout +
                                                          error.stderr)
                raise
            (evidence /
             f'{box.sandbox_id}-seed.log').write_text(seeded.stdout +
                                                      seeded.stderr)
        if bigquery:
            if captured and not business_bigquery.same_sources(
                    captured['service'].get('bigquery'), bigquery):
                raise ValueError('BigQuery dependencies differ from capture')
            if not business_bigquery.state(box)['rows']:
                raise ValueError('Original BigQuery seed left an empty CRM')
        if sheets:
            if captured and not business_sheets.same_sources(
                    captured['service'].get('sheets'), sheets):
                raise ValueError('Sheets fixture sources differ from capture')
            business_sheets.set_folder(task)
            business_sheets.validate_seed(box, task)
        if forms:
            business_forms.validate_seed()
            if captured and not business_forms.same_sources(
                    captured['service'].get('forms'), forms):
                raise ValueError('Forms fixture sources differ from capture')
            business_forms.start_cli(stack)
        if mail:
            if service == 'woocommerce':
                business_mail.assert_empty(task)
            if captured and not business_mail.same_sources(
                    captured['service'].get('mail'), mail):
                raise ValueError('Mail sources differ from the capture')
        transfer_out(box, workdir)
        for index, port in enumerate(ports):
            expose(box, port, port, 8083 + index, stack)
        identity = tokens(task)
        if service == 'canvas':
            os.environ.update(CANVAS_API_TOKEN=identity.canvas_api_token,
                              CANVAS_DOMAIN='localhost:20001',
                              CANVAS_API_BASE='http://localhost:10001/api/v1')
        else:
            os.environ.update(
                WORDPRESS_SITE_URL=identity.woocommerce_site_url,
                WOOCOMMERCE_CONSUMER_KEY=identity.woocommerce_api_key,
                WOOCOMMERCE_CONSUMER_SECRET=identity.woocommerce_api_secret,
                WOOCOMMERCE_API_BASE=identity.woocommerce_site_url.rstrip('/')
                + '/wp-json/wc/v3')
        from server.seed.travel_video import serve as original_tools
        stack.enter_context(original_tools(task, workdir))
        images = json.loads(
            command(
                box, 'sudo docker image inspect '
                '$(sudo docker image ls -q --no-trunc)').stdout)
        record = {
            'sandbox_id':
            box.sandbox_id,
            'task':
            task,
            'service':
            service,
            'template':
            template,
            'inputs_sha256':
            hashes,
            'images': [{
                key: row[key]
                for key in ('Id', 'RepoTags', 'RepoDigests')
            } for row in images],
            'dependency_sources':
            json.loads((REPO / 'server/business-sources.json').read_text())
        }
        if remote_mcp:
            record['mcp'] = remote_mcp
        if mail:
            record['mail'] = mail
        if sheets:
            record['sheets'] = sheets
        if bigquery:
            record['bigquery'] = bigquery
        if forms:
            record['forms'] = forms
        if captured:
            fixture = (woocommerce_fixture
                       if service == 'woocommerce' else canvas_fixture)
            state = fixture.api_state(task)
            actual = (woocommerce_fixture.state_hashes(
                state, captured.get('sampled_related_ids', False)) if service
                      == 'woocommerce' else canvas_fixture.state_hashes(
                          state, task))
            if actual != captured['api_sha256']:
                (evidence / f'{box.sandbox_id}-restore.json'
                 ).write_text(json.dumps(state, indent=2) + '\n')
                changed = sorted(
                    path for path in actual
                    if actual[path] != captured['api_sha256'].get(path))
                raise ValueError(f'Restored {service} API differs: ' +
                                 ', '.join(changed))
            record['fixture'] = {
                'sha256':
                captured['sha256'],
                'api_sha256':
                actual,
                'source_sha256':
                hashlib.sha256((fixture.folder(task) /
                                'source.json').read_bytes()).hexdigest(),
            }
        path = evidence / f'{box.sandbox_id}.json'
        path.write_text(json.dumps(record, indent=2) + '\n')
        os.environ['BUSINESS_SOURCE_RECORD'] = str(path)
        yield record


def restore_environment(previous):
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def grade(task, workdir, launch_time):
    if task != os.environ.get('BUSINESS_TASK'):
        raise ValueError('Grader task does not match the live fixture')
    box = Sandbox.connect(os.environ['BUSINESS_SANDBOX_ID'])
    transfer_in(box, workdir)
    command(box, 'printf \'{}\' > /tmp/result-log.json')
    line = ('cd /opt/toolathlon && sudo -E ' +
            (business_sheets.REDIRECT if task
             in ('woocommerce-stock-alert', 'update-material-inventory',
                 'woocommerce-customer-survey',
                 'woocommerce-product-recall') else business_bigquery.REDIRECT
             if task == 'woocommerce-new-welcome' else '') +
            'uv run -m tasks.finalpool.' + task +
            '.evaluation.main --agent_workspace /work '
            '--res_log_file /tmp/result-log.json')
    source = original(f'tasks/finalpool/{task}/evaluation/main.py').decode()
    if '--groundtruth_workspace' in source:
        line += (' --groundtruth_workspace /opt/toolathlon/tasks/finalpool/' +
                 task + '/groundtruth_workspace')
    if launch_time and '--launch_time' in source:
        line += ' --launch_time ' + shlex.quote(launch_time)
    try:
        result = box.commands.run(line, timeout=600)
    except CommandExitException as error:
        result = error
    print(result.stdout, end='')
    print(result.stderr, end='')
    return result.exit_code
