import gzip
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from server.fakes.hub_viewer import DEFAULTS, TOOL, folder, key  # noqa: E402

URL = 'https://huggingface.co/mcp'
API = 'https://huggingface.co/api/datasets/'
# The Dataset Viewer pages an agent reaches for: the first page at the
# tool's default and at every round limit up to its cap, and the next two
# pages at the default. A request outside this set is answered by the fake's
# own refusal, never by a page nobody captured.
PAGES = ((0, 5), (0, 10), (0, 20), (0, 50), (0, 100), (5, 5), (10, 10))


def datasets(task):
    """The datasets a task's Hub fixture pins, with the revision it pins."""
    shared = REPO / 'task/toolathlon' / task / 'shared'
    if task == 'dataset-license-issue':
        module = script(shared / 'build_fixture.py')
        return {
            repo: revision
            for kind, repo, revision in module.CARDS if kind == 'datasets'
        }
    if task == 'verl-dataset':
        # Seeded from upstream's own copy of the repository's one file, so
        # there is no Hub revision to pin; the receipt records the live one.
        return {script(shared / 'seed_hf.py').REPO_ID: None}
    raise KeyError(task)


def script(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Live:

    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
        self.headers = {
            'Accept': 'application/json, text/event-stream',
            'Content-Type': 'application/json'
        }
        reply = self.rpc(
            'initialize', {
                'protocolVersion': '2025-03-26',
                'capabilities': {},
                'clientInfo': {
                    'name': 'vfs-bench capture',
                    'version': '0'
                }
            })
        self.server = reply['result']['serverInfo']
        self.rpc('notifications/initialized', {}, notify=True)

    def rpc(self, method, params, notify=False):
        body = {'jsonrpc': '2.0', 'method': method, 'params': params}
        if not notify:
            body['id'] = 1
        response = self.session.post(URL,
                                     headers=self.headers,
                                     json=body,
                                     timeout=180)
        response.raise_for_status()
        session = response.headers.get('Mcp-Session-Id')
        if session:
            self.headers['Mcp-Session-Id'] = session
        if notify:
            return None
        if response.headers.get('Content-Type',
                                '').startswith('text/event-stream'):
            data = [
                line[len('data:'):].strip()
                for line in response.text.splitlines()
                if line.startswith('data:')
            ]
            body = json.loads(data[-1])
        else:
            body = response.json()
        if 'error' in body:
            raise RuntimeError(body['error'])
        return body

    def call(self, arguments):
        return self.rpc('tools/call', {
            'name': TOOL,
            'arguments': arguments
        })['result']


def configs(text):
    """Config and split pairs from a captured `dataset_structure` table."""
    pairs = []
    rows = text.split('### Configs and Splits', 1)[-1].split('###', 1)[0]
    for line in rows.splitlines():
        cells = [cell.strip(' `') for cell in line.strip('|').split('|')]
        if len(cells) >= 2 and cells[0] not in ('Config', '---') and not set(
                cells[0]) <= {'-', ':'}:
            pairs.append((cells[0], cells[1]))
    return pairs


def requests_for(live, repos):
    """Every argument set captured for one task, in a stated order."""
    plans = []
    for repo in repos:
        for repo_type in (None, 'dataset'):
            base = {'repo_ids': [repo]}
            if repo_type:
                base['repo_type'] = repo_type
            plans += [{
                **base, 'operations': ops
            } for ops in (['overview', 'dataset_structure'],
                          ['dataset_structure'], ['dataset_preview'],
                          ['dataset_structure', 'dataset_preview'],
                          ['overview', 'dataset_structure', 'dataset_preview'])
                      ]
    if len(repos) > 1:
        for ops in (['overview', 'dataset_structure'], ['dataset_structure']):
            plans.append({
                'repo_ids': list(repos),
                'repo_type': 'dataset',
                'operations': ops
            })
    return plans


def capture(task):
    """Ask the live Hub MCP server what the fake refuses, and keep it."""
    pinned = datasets(task)
    live = Live()
    started = datetime.now(timezone.utc).isoformat()
    responses = []
    seen = set()

    def take(arguments):
        if key(arguments) in seen:
            return None
        seen.add(key(arguments))
        result = live.call(arguments)
        responses.append({'arguments': arguments, 'result': result})
        print(task,
              json.dumps(arguments),
              '->',
              len(result['content'][0]['text']),
              'chars',
              flush=True)
        return result

    for arguments in requests_for(live, list(pinned)):
        result = take(arguments)
        if result is None or 'dataset_structure' not in arguments[
                'operations'] or len(arguments['repo_ids']) != 1:
            continue
        # Every config and split the structure names gets its pages,
        # with and without the type spelled, at each captured page.
        for config, split in configs(result['content'][0]['text']):
            for repo_type in (None, 'dataset'):
                for offset, limit in PAGES:
                    arguments = {
                        'repo_ids': arguments['repo_ids'],
                        'operations': ['dataset_preview'],
                        'config': config,
                        'split': split
                    }
                    if repo_type:
                        arguments['repo_type'] = repo_type
                    if (offset, limit) != (DEFAULTS['offset'],
                                           DEFAULTS['limit']):
                        arguments.update(offset=offset, limit=limit)
                    take(arguments)
    revisions = {}
    for repo, revision in pinned.items():
        about = live.session.get(API + repo, timeout=60)
        about.raise_for_status()
        revisions[repo] = {
            'pinned': revision,
            'live': about.json().get('sha'),
            'lastModified': about.json().get('lastModified')
        }
    payload = {
        'task': task,
        'server': live.server,
        'started_at': started,
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'revisions': revisions,
        'responses': responses
    }
    data = gzip.compress(json.dumps(payload, ensure_ascii=False).encode(),
                         mtime=0)
    folder(task).mkdir(parents=True, exist_ok=True)
    (folder(task) / 'responses.json.gz').write_bytes(data)
    (folder(task) / 'source.json').write_text(
        json.dumps(
            {
                'source': URL,
                'tool': TOOL,
                'server': live.server,
                'captured_at': payload['captured_at'],
                'revisions': revisions,
                'responses': len(responses),
                'sha256': {
                    'responses.json.gz': hashlib.sha256(data).hexdigest()
                }
            },
            indent=2) + '\n')
    print(task, len(responses), 'responses captured from', live.server)


def verify(task):
    """The receipt's hash holds and every pinned dataset was captured."""
    from server.fakes.hub_viewer import load
    data = load(task)
    pinned = datasets(task)
    for repo, revision in pinned.items():
        if revision and data['revisions'][repo]['pinned'] != revision:
            raise ValueError(f'{task}: {repo} pinned revision moved')
        if not any(repo in item['arguments']['repo_ids']
                   for item in data['responses']):
            raise ValueError(f'{task}: no captured viewer answer for {repo}')
    for item in data['responses']:
        if item['result'].get('isError'):
            raise ValueError(f'{task}: captured an error for '
                             f'{json.dumps(item["arguments"])}')
    drifted = [
        repo for repo, about in data['revisions'].items()
        if about['pinned'] and about['live'] != about['pinned']
    ]
    print(
        task, len(data['responses']), 'viewer answers;',
        'live revisions match the pins'
        if not drifted else f'captured after the pin moved on: {drifted}')


if __name__ == '__main__':
    action, names = sys.argv[1], sys.argv[2:] or [
        'dataset-license-issue', 'verl-dataset'
    ]
    for name in names:
        {'capture': capture, 'verify': verify}[action](name)
