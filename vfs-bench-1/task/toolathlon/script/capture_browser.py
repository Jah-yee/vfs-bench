"""Capture original browser-task sources without reconstructing task data."""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

from server.seed.kubernetes import original
from task.toolathlon.script.capture_experiments_notion import value

REPO = Path(__file__).resolve().parents[3]


def publish(task, files, source):
    destination = REPO / 'task/toolathlon' / task / 'shared/fixtures'
    if (destination / 'source.json').exists():
        raise FileExistsError('The original capture already exists')
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (destination / name).write_bytes(data)
    paths = ['docs/task.md', 'preprocess/main.py', 'evaluation/main.py']
    record = {
        **source, 'captured_at': datetime.now(timezone.utc).isoformat(),
        'source_sha256': {
            f'tasks/finalpool/{task}/{name}':
            hashlib.sha256(
                original(f'tasks/finalpool/{task}/{name}')).hexdigest()
            for name in paths
        },
        'sha256': {
            name: hashlib.sha256(data).hexdigest()
            for name, data in files.items()
        }
    }
    (destination /
     'source.json').write_text(json.dumps(record, indent=2) + '\n')


def preview():
    task = 'k8s-pr-preview-testing'
    text = original(f'tasks/finalpool/{task}/docs/task.md').decode()
    branch, repository = re.findall(r'`([^`]+)`', text)[:2]
    url = f'https://github.com/{repository}.git'
    with tempfile.TemporaryDirectory(
            prefix='toolathlon-preview-source-') as directory:
        checkout = Path(directory) / 'repo.git'
        subprocess.run([
            'git', 'clone', '--bare', '--single-branch', '--branch', branch,
            url,
            str(checkout)
        ],
                       check=True)
        revision = subprocess.check_output(
            ['git', '-C',
             str(checkout), 'rev-parse', 'refs/heads/' + branch],
            text=True).strip()
        bundle = Path(directory) / 'repository.bundle'
        subprocess.run([
            'git', '-C',
            str(checkout), 'bundle', 'create',
            str(bundle), 'refs/heads/' + branch
        ],
                       check=True)
        publish(task, {'repository.bundle': bundle.read_bytes()}, {
            'url': url,
            'branch': branch,
            'revision': revision
        })


def job(task='notion-find-job', title='Job Finder'):
    reads = []

    def read(method, body):
        response = requests.post('https://www.notion.so/api/v3/' + method,
                                 json=body,
                                 timeout=60)
        response.raise_for_status()
        result = response.json()
        reads.append({'method': method, 'request': body, 'response': result})
        return result

    def page(page_id):
        result = read(
            'loadPageChunk', {
                'pageId': page_id,
                'limit': 100,
                'cursor': {
                    'stack': []
                },
                'chunkNumber': 0,
                'verticalColumns': False
            })
        if result['cursor']['stack']:
            raise ValueError('Original Notion page requires another chunk')
        return result['recordMap']

    guide = 'global_preparation/how2register_accounts.md'
    source = original(guide).decode()
    link = re.search(r'\[Notion Source Page\]\(([^)]+)\)', source).group(1)
    identifier = link.rsplit('-', 1)[1]
    import uuid
    parent = str(uuid.UUID(identifier))
    records = page(parent)
    candidates = [
        value(row) for row in records['block'].values()
        if value(row).get('properties', {}).get('title') == [[title]]
    ]
    if len(candidates) != 1 or candidates[0]['parent_id'] != parent:
        raise ValueError('The original Job Finder source changed')
    root = candidates[0]
    records = page(root['id'])
    blocks = [
        value(row) for row in records['block'].values() if value(row).get(
            'type') in {'collection_view', 'collection_view_page'}
    ]
    databases = []
    for block in blocks:
        collection = value(records['collection'][block['collection_id']])
        view = value(records['collection_view'][block['view_ids'][0]])
        rows = read(
            'queryCollection', {
                'collection': {
                    'id': collection['id'],
                    'spaceId': collection['space_id']
                },
                'collectionView': {
                    'id': view['id'],
                    'spaceId': view['space_id']
                },
                'loader': {
                    'type': 'reducer',
                    'reducers': {
                        'collection_group_results': {
                            'type': 'results',
                            'limit': 1000
                        }
                    },
                    'searchQuery': '',
                    'userTimeZone': 'UTC'
                }
            })
        result = rows['result']['reducerResults']['collection_group_results']
        if result['hasMore'] or len(set(result['blockIds'])) != len(
                result['blockIds']):
            raise ValueError('Incomplete original Notion row inventory')
        for row_id in result['blockIds']:
            page(row_id)
        databases.append({
            'id': block['id'],
            'collection_id': collection['id'],
            'rows': result['blockIds']
        })
    raw = (json.dumps(reads, indent=2) + '\n').encode()
    publish(task, {'public-api.json.gz': gzip.compress(raw, mtime=0)}, {
        'url': link,
        'parent_page_id': parent,
        'page_id': root['id'],
        'databases': databases,
        'guide_sha256': hashlib.sha256(source.encode()).hexdigest()
    })
    print('Captured original', title, 'databases:', len(databases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'task',
        choices=['k8s-pr-preview-testing', 'notion-find-job', 'notion-movies'])
    task = parser.parse_args().task
    if task == 'notion-movies':
        job(task, 'Ultimate Movie Tracker')
    else:
        (preview if task == 'k8s-pr-preview-testing' else job)()


if __name__ == '__main__':
    main()
