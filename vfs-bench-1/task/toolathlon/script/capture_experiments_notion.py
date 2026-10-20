"""Capture the original public Notion page, database schema and all rows."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from server.seed.kubernetes import original

REPO = Path(__file__).resolve().parents[3]
DEST = REPO / 'task/toolathlon/experiments-recordings/shared/fixtures/notion'
PAGE = '27ad10a4-8436-8033-aff3-fda661048897'
URL = ('https://amazing-wave-b38.notion.site/mcp_experiments_recordings-' +
       PAGE.replace('-', ''))


def value(record):
    result = record
    while 'value' in result:
        result = result['value']
    return result


def main():
    if DEST.exists():
        raise FileExistsError('The original Notion capture already exists')
    reads = []

    def read(method, body):
        response = requests.post('https://www.notion.so/api/v3/' + method,
                                 json=body,
                                 timeout=60)
        response.raise_for_status()
        result = response.json()
        reads.append({'method': method, 'request': body, 'response': result})
        return result

    page = read(
        'loadPageChunk', {
            'pageId': PAGE,
            'limit': 100,
            'cursor': {
                'stack': []
            },
            'chunkNumber': 0,
            'verticalColumns': False
        })
    if page['cursor']['stack']:
        raise ValueError('Source page needs another chunk')
    records = page['recordMap']
    parent = value(records['block'][PAGE])
    guide = 'global_preparation/how2register_accounts.md'
    if parent['parent_id'].replace('-', '') not in original(guide).decode():
        raise ValueError(
            'Source page is not under the published original parent')
    if len(parent['content']) != 1:
        raise ValueError('The source page structure changed')
    block = value(records['block'][parent['content'][0]])
    if block['type'] != 'collection_view_page' or len(block['view_ids']) != 1:
        raise ValueError('The source database structure changed')
    collection = value(records['collection'][block['collection_id']])
    view = value(records['collection_view'][block['view_ids'][0]])
    if view.get('query2', {}).get('filter') or view.get('query',
                                                        {}).get('filter'):
        raise ValueError('Source database view is filtered')
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
    if result['hasMore'] or len(
            result['blockIds']) != rows['result']['sizeHint']:
        raise ValueError('Incomplete original Notion row inventory')
    for row_id in result['blockIds']:
        row = value(rows['recordMap']['block'][row_id])
        if row.get('content'):
            raise ValueError('Capture the original row child blocks first')
    DEST.mkdir(parents=True)
    data = (json.dumps(reads, indent=2) + '\n').encode()
    (DEST / 'public-api.json').write_bytes(data)
    paths = ['docs/task.md', 'preprocess/main.py', 'token_key_session.py']
    receipt = {
        'url': URL,
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'page_id': PAGE,
        'database_id': block['id'],
        'rows': result['blockIds'],
        'source_sha256': {
            f'tasks/finalpool/experiments-recordings/{name}':
            hashlib.sha256(
                original(f'tasks/finalpool/experiments-recordings/{name}')).
            hexdigest()
            for name in paths
        },
        'sha256': {
            'public-api.json': hashlib.sha256(data).hexdigest()
        }
    }
    receipt['source_sha256'][guide] = hashlib.sha256(
        original(guide)).hexdigest()
    (DEST / 'source.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
