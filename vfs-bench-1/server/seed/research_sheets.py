"""Original Sheets preprocessing and grading against one local API per arm."""
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from server.clients import gws
from server.fakes.sheet_formats import serve as formats
from server.seed.business import restore_environment
from server.seed.business_sheets import (mirage_source, remove_source, seed,
                                         source_folder)
from server.seed.kubernetes import UPSTREAM, original

REPO = Path(__file__).resolve().parents[2]
TASKS = ('gdp-cr5-analysis', 'llm-training-dataset',
         'inter-final-performance-analysis', 'vlm-history-completer')
CURRENT = None


def image_inputs():
    # The digest of these bytes names the image, so reading Mirage's folder
    # rather than its last commit is what makes a fix to the fake rebuild
    # instead of matching the tag an unfixed image already holds.
    files = mirage_source('integ/server/kit', 'integ/server/gws',
                          'integ/prisma/gws.prisma', 'integ/fixtures/gws')
    files.update({
        name: (REPO / name).read_bytes()
        for name in ('docker/sheets.Dockerfile', 'docker/package.json',
                     'docker/package-lock.json',
                     'server/fakes/research_gws.mjs')
    })
    return files


def image_name():
    files = image_inputs()
    hashes = {
        name: hashlib.sha256(data).hexdigest()
        for name, data in files.items()
    }
    digest = hashlib.sha256(json.dumps(hashes,
                                       sort_keys=True).encode()).hexdigest()
    name = 'toolathlon-sheets:' + digest[:16]
    if subprocess.run(['docker', 'image', 'inspect', name],
                      stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode:
        with tempfile.TemporaryDirectory(prefix='sheets-build-') as directory:
            for path, data in files.items():
                target = Path(directory) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            subprocess.run([
                'docker', 'build', '--file',
                str(Path(directory) / 'docker/sheets.Dockerfile'), '--tag',
                name, directory
            ],
                           check=True)
    return name, hashes


def source_tree(task, directory):
    """Private generated IDs and credentials never modify the checkout."""
    prefix = f'tasks/finalpool/{task}'
    data = subprocess.check_output([
        'git', '-C',
        str(UPSTREAM), 'archive', 'HEAD', prefix,
        'configs/token_key_session_example.py',
        'configs/global_configs_example.py', 'utils'
    ])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(directory, filter='data')
    (directory / 'configs/token_key_session_example.py').rename(
        directory / 'configs/token_key_session.py')
    (directory / 'configs/global_configs_example.py').rename(
        directory / 'configs/global_configs.py')
    expiry = datetime.now(timezone.utc) + timedelta(days=1)
    (directory / 'configs/google_credentials.json').write_text(
        json.dumps({
            'token':
            gws.TOKEN,
            'refresh_token':
            gws.TOKEN,
            'client_id':
            'fixture',
            'client_secret':
            'fixture',
            'token_uri':
            gws.base() + '/token',
            'expiry':
            expiry.isoformat().replace('+00:00', 'Z'),
            'scopes': [
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
        }))
    redirect = directory / 'redirect'
    redirect.mkdir()
    (redirect / 'sitecustomize.py').write_bytes(
        (REPO / 'redirect/eval_shim/gws_redirect.py').read_bytes())
    return directory / prefix, hashlib.sha256(data).hexdigest()


def run(directory, task, module, args, timeout):
    # The foreign task uses Toolathlon's own installed, locked interpreter.
    return subprocess.run(
        [
            str(UPSTREAM / '.venv/bin/python'), '-m',
            f'tasks.finalpool.{task}.{module}.main', *args
        ],
        cwd=directory,
        env={
            **os.environ, 'PYTHONPATH': str(directory / 'redirect'),
            'PYTHONDONTWRITEBYTECODE': '1',
            'GWS_MOCK_URL': gws.base()
        },
        capture_output=True,
        text=True,
        timeout=timeout)


@contextmanager
def serve(task, workdir):
    global CURRENT
    previous = CURRENT
    saved = {
        key: os.environ.get(key)
        for key in ('GWS_URL', 'DRIVE_FOLDER_ID')
    }
    with ExitStack() as stack:
        stack.callback(restore_environment, saved)
        directory = Path(
            stack.enter_context(
                tempfile.TemporaryDirectory(prefix='sheets-',
                                            dir=REPO / 'state/research')))
        image, hashes = image_name()
        container = subprocess.check_output([
            'docker', 'run', '--detach', '--rm', '--publish',
            '127.0.0.1::19999', image
        ],
                                            text=True).strip()
        stack.callback(subprocess.run, ['docker', 'rm', '-f', container],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        port = subprocess.check_output(
            ['docker', 'port', container, '19999/tcp'],
            text=True).strip().rsplit(':', 1)[1]
        base = 'http://127.0.0.1:' + port
        for _ in range(120):
            try:
                if requests.get(base + '/_kit/health', timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(.25)
        else:
            logs = subprocess.check_output(['docker', 'logs', container],
                                           stderr=subprocess.STDOUT,
                                           text=True)
            raise RuntimeError('Sheets fixture startup failed: ' + logs)
        endpoint = stack.enter_context(formats(base))
        os.environ['GWS_URL'] = endpoint
        gws.reset()
        seed(task)
        source = json.loads((source_folder(task) / 'source.json').read_text())
        task_tree, source_sha = source_tree(task, directory)
        result = run(directory, task, 'preprocess',
                     ['--agent_workspace', str(workdir)], 180)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        folder = (task_tree / 'files/folder_id.txt').read_text().strip()
        os.environ['DRIVE_FOLDER_ID'] = folder
        files = gws.call(
            'GET', '/drive/v3/files?q=' +
            gws.quote(f"'{folder}' in parents and trashed=false"))['files']
        if len(files) != 1 or files[0]['name'] != source['title']:
            raise ValueError('Original preprocessing did not copy its Sheet')
        sheet_id = files[0]['id']
        original_sheet = gws.grid(source['sheet_id'])
        copied = gws.grid(sheet_id)
        if copied['sheets'] != original_sheet['sheets']:
            raise ValueError('Copied values or formatting differ from source')
        remove_source(task)
        record = {
            'original_tree_sha256':
            source_sha,
            'source':
            source,
            'folder_id':
            folder,
            'sheet_id':
            sheet_id,
            'inputs_sha256':
            hashes,
            'image_id':
            subprocess.check_output(
                ['docker', 'image', 'inspect', '--format', '{{.Id}}', image],
                text=True).strip(),
            'seed_sha256':
            hashlib.sha256(
                json.dumps(copied['sheets'],
                           sort_keys=True).encode()).hexdigest(),
            'preprocess_sha256':
            hashlib.sha256(
                original(
                    f'tasks/finalpool/{task}/preprocess/main.py')).hexdigest()
        }
        CURRENT = {'task': task, 'directory': directory, 'record': record}
        try:
            yield record
        finally:
            CURRENT = previous


def grade(task, workdir, launch_time, timeout):
    if not CURRENT or CURRENT['task'] != task:
        raise RuntimeError('The task does not own an active Sheets fixture')
    directory = CURRENT['directory']
    root = directory / 'tasks/finalpool' / task
    log = directory / 'result-log.json'
    log.write_text('{}')
    args = ['--agent_workspace', str(workdir), '--res_log_file', str(log)]
    if (root / 'groundtruth_workspace').is_dir():
        args += [
            '--groundtruth_workspace',
            str(root / 'groundtruth_workspace')
        ]
    if launch_time and '--launch_time' in (root /
                                           'evaluation/main.py').read_text():
        args += ['--launch_time', launch_time]
    result = run(directory, task, 'evaluation', args, timeout)
    print(result.stdout, end='')
    print(result.stderr, end='')
    return result.returncode
