"""Render the captured public Notion source in Mirage's fixture schema."""
import hashlib
import json
from datetime import datetime, timezone

from task.toolathlon.script.capture_experiments_notion import (DEST, PAGE,
                                                               REPO, value)


def main():
    source = json.loads((DEST / 'source.json').read_text())
    raw = (DEST / 'public-api.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != source['sha256']['public-api.json']:
        raise ValueError('Original Notion capture checksum mismatch')
    reads = json.loads(raw)
    tree, query = (r['response'] for r in reads)
    records = tree['recordMap']
    root = value(records['block'][PAGE])
    block = value(records['block'][source['database_id']])
    schema = value(records['collection'][block['collection_id']])['schema']
    fixture = json.loads(
        (REPO / 'server/clients/notion_empty.json').read_text())

    def common(row):

        def instant(key):
            return datetime.fromtimestamp(row[key] / 1000,
                                          timezone.utc).isoformat().replace(
                                              '+00:00', 'Z')

        return {
            'id':
            row['id'],
            'createdTime':
            instant('created_time'),
            'lastEditedTime':
            instant('last_edited_time'),
            'createdBy':
            row.get('created_by_id', fixture['meta']['createdBy']),
            'lastEditedBy':
            row.get('last_edited_by_id', fixture['meta']['lastEditedBy']),
            'url':
            'https://www.notion.so/' + row['id'].replace('-', '')
        }

    title = ''.join(r[0] for r in root['properties']['title'])
    rich_title = [{
        'type': 'text',
        'plain_text': title,
        'text': {
            'content': title
        }
    }]
    fixture['pages'].append({
        **common(root), 'parentType': 'workspace',
        'parentId': None,
        'titleText': title,
        'propertiesJson': {
            'title': {
                'type': 'title',
                'title': rich_title
            }
        }
    })
    properties = {}
    for key, prop in schema.items():
        kind = {
            'text': 'rich_text',
            'title': 'title',
            'number': 'number'
        }[prop['type']]
        properties[prop['name']] = {
            'id': key,
            'name': prop['name'],
            'type': kind,
            kind: {
                'format': 'number'
            } if kind == 'number' else {}
        }
    fixture['databases'].append({
        **common(block), 'parentType': 'page_id',
        'parentId': PAGE,
        'titleText': title,
        'titleJson': rich_title,
        'propertiesJson': properties
    })
    fixture['blocks'].append({
        **{
            key: val
            for key, val in common(block).items() if key != 'url'
        }, 'parentId': PAGE,
        'position': 0,
        'type': 'child_database',
        'payloadJson': {
            'title': title
        },
        'hasChildren': False
    })
    results = query['result']['reducerResults']['collection_group_results']
    if results['hasMore'] or results['blockIds'] != source['rows']:
        raise ValueError('Original row inventory changed')
    for position, row_id in enumerate(source['rows']):
        row = value(query['recordMap']['block'][row_id])
        if row.get('properties') or row.get('content'):
            raise ValueError('Source rows are no longer blank')
        cells = {}
        for name, prop in properties.items():
            kind = prop['type']
            cells[name] = {
                'id': prop['id'],
                'type': kind,
                kind: None if kind == 'number' else []
            }
        fixture['pages'].append({
            **common(row), 'parentType': 'database_id',
            'parentId': block['id'],
            'titleText': '',
            'propertiesJson': cells,
            'position': position
        })
    output = DEST / 'rendered/notion/experiments-recordings.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(fixture, indent=2) + '\n')
    (DEST.parents[1] / 'notion.json').write_text(
        json.dumps(
            {
                'workspace': 'experiments-recordings',
                'page_id': PAGE,
                'page_title': title
            },
            indent=2) + '\n')


if __name__ == '__main__':
    main()
