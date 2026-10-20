"""Render captured original Notion blocks, schemas and rows."""
import gzip
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from task.toolathlon.script.capture_experiments_notion import value

REPO = Path(__file__).resolve().parents[3]


def rich(runs):
    result = []
    for text, *rest in runs or []:
        annotations = {
            'bold': False,
            'italic': False,
            'strikethrough': False,
            'underline': False,
            'code': False,
            'color': 'default'
        }
        link = None
        for annotation in rest[0] if rest else []:
            kind, *args = annotation
            if kind == 'a':
                link = {'url': args[0]}
            elif kind in {'b', 'i', 's', '_', 'c'}:
                annotations[{
                    'b': 'bold',
                    'i': 'italic',
                    's': 'strikethrough',
                    '_': 'underline',
                    'c': 'code'
                }[kind]] = True
            elif kind == 'h':
                annotations['color'] = args[0]
            else:
                raise ValueError('Unmapped original rich text annotation: ' +
                                 kind)
        result.append({
            'type': 'text',
            'text': {
                'content': text,
                'link': link
            },
            'plain_text': text,
            'href': link['url'] if link else None,
            'annotations': annotations
        })
    return result


def plain(runs):
    return ''.join(run[0] for run in runs or [])


def derive(task):
    folder = REPO / 'task/toolathlon' / task / 'shared/fixtures'
    source = json.loads((folder / 'source.json').read_text())
    raw = (folder / 'public-api.json.gz').read_bytes()
    assert hashlib.sha256(
        raw).hexdigest() == source['sha256']['public-api.json.gz']
    records = {}
    for read in json.loads(gzip.decompress(raw)):
        for kind, rows in read['response'].get('recordMap', {}).items():
            if isinstance(rows, dict):
                records.setdefault(kind, {}).update({
                    key: value(row)
                    for key, row in rows.items()
                })
    blocks = records['block']
    root_id = source['page_id']
    databases = source.get('databases', [{
        'id': source.get('database_id'),
        'rows': source.get('rows')
    }])
    db_by_collection = {
        blocks[db['id']]['collection_id']: db
        for db in databases
    }
    row_ids = {row: db['id'] for db in databases for row in db['rows']}
    fixture = json.loads(
        (REPO / 'server/clients/notion_empty.json').read_text())
    fixture['meta'].update(workspaceName=task, workspaceId=root_id)

    def timestamp(milliseconds):
        return datetime.fromtimestamp(milliseconds / 1000,
                                      timezone.utc).isoformat().replace(
                                          '+00:00', 'Z')

    def common(row):
        return {
            'id':
            row['id'],
            **{
                target: timestamp(row[key])
                for key, target in [('created_time', 'createdTime'),
                                    ('last_edited_time', 'lastEditedTime')]
            }, 'createdBy':
            row.get('created_by_id', fixture['meta']['createdBy']),
            'lastEditedBy':
            row.get('last_edited_by_id', fixture['meta']['lastEditedBy'])
        }

    def options(prop):
        return [{
            'id': item['id'],
            'name': item['value'],
            'color': item['color']
        } for item in prop.get('options', [])]

    def properties(row, schema):
        result = {}
        for key, prop in schema.items():
            kind = {'text': 'rich_text'}.get(prop['type'], prop['type'])
            runs = row.get('properties', {}).get(key, [])
            text = plain(runs)
            if kind in ('rich_text', 'title'):
                data = rich(runs)
            elif kind == 'number':
                data = float(text) if text else None
            elif kind in ('select', 'multi_select'):
                selected = [
                    item for item in options(prop)
                    if item['name'] in text.split(',')
                ]
                if text and not selected:
                    raise ValueError('Unknown captured select option: ' + text)
                data = selected if kind == 'multi_select' else (
                    selected[0] if selected else None)
            elif kind == 'url':
                data = text or None
            else:
                raise ValueError('Unmapped original property: ' + kind)
            result[prop['name']] = {'id': key, 'type': kind, kind: data}
        return result

    seen = set()

    def walk(identifier, parent, position=0):
        if identifier in seen:
            return
        seen.add(identifier)
        row = blocks[identifier]
        kind = row['type']
        children = row.get('content', [])
        base = {**common(row), 'parentId': parent, 'position': position}
        if kind in ('collection_view', 'collection_view_page'):
            if not row.get('collection_id'):
                # Empty copied linked views have no database to expose.
                fixture['blocks'].append({
                    **base, 'type': 'unsupported',
                    'payloadJson': {},
                    'hasChildren': False
                })
                return
            collection_id = row['collection_id']
            if collection_id not in db_by_collection:
                raise ValueError('Uncaptured descendant database')
            db = db_by_collection[collection_id]
            if identifier != db['id']:
                raise ValueError(
                    'Linked database view needs an explicit mapping')
            collection = records['collection'][collection_id]
            title = plain(collection['name'])
            schema = {}
            for key, prop in collection['schema'].items():
                typ = {'text': 'rich_text'}.get(prop['type'], prop['type'])
                detail = {
                    'options': options(prop)
                } if typ in ('select', 'multi_select') else (
                    {
                        'format': prop.get('number_format', 'number')
                    } if typ == 'number' else {})
                schema[prop['name']] = {
                    'id': key,
                    'name': prop['name'],
                    'type': typ,
                    typ: detail
                }
            fixture['databases'].append({
                **base, 'parentType':
                'page_id',
                'titleText':
                title,
                'titleJson':
                rich(collection['name']),
                'propertiesJson':
                schema,
                'url':
                'https://www.notion.so/' + identifier.replace('-', '')
            })
            fixture['blocks'].append({
                **base, 'type': 'child_database',
                'payloadJson': {
                    'title': title
                },
                'hasChildren': False
            })
            for i, row_id in enumerate(db['rows']):
                walk(row_id, identifier, i)
            return
        if kind == 'page':
            if identifier in row_ids:
                collection = records['collection'][blocks[parent]
                                                   ['collection_id']]
                props = properties(row, collection['schema'])
                parent_type = 'database_id'
            else:
                props = properties(
                    row, {'title': {
                        'name': 'title',
                        'type': 'title'
                    }})
                parent_type = 'workspace' if parent is None else 'page_id'
            fixture['pages'].append({
                **base, 'parentType':
                parent_type,
                'titleText':
                plain(row.get('properties', {}).get('title')),
                'propertiesJson':
                props,
                'url':
                'https://www.notion.so/' + identifier.replace('-', '')
            })
            if identifier != root_id and identifier not in row_ids:
                fixture['blocks'].append({
                    **base, 'type': 'child_page',
                    'payloadJson': {
                        'title': plain(row.get('properties', {}).get('title'))
                    },
                    'hasChildren': bool(children)
                })
        else:
            typ = {
                'text': 'paragraph',
                'sub_header': 'heading_2',
                'sub_sub_header': 'heading_3'
            }.get(kind, kind)
            payload = {}
            if typ in ('paragraph', 'heading_2', 'heading_3', 'quote',
                       'callout'):
                payload = {
                    'rich_text': rich(row.get('properties', {}).get('title')),
                    'color': row.get('format', {}).get('block_color',
                                                       'default')
                }
                if typ == 'callout':
                    icon = row.get('format', {}).get('page_icon')
                    if icon:
                        payload['icon'] = ({
                            'type': 'external',
                            'external': {
                                'url': icon
                            }
                        } if icon.startswith(('http', '/')) else {
                            'type': 'emoji',
                            'emoji': icon
                        })
            elif typ in ('image', 'video'):
                url = plain(row.get('properties', {}).get('source'))
                payload = {
                    'type': 'external',
                    'external': {
                        'url': url
                    },
                    'caption': []
                }
            elif typ not in ('divider', 'column', 'column_list'):
                raise ValueError('Unmapped original block: ' + typ)
            fixture['blocks'].append({
                **base, 'type': typ,
                'payloadJson': payload,
                'hasChildren': bool(children)
            })
        for i, child in enumerate(children):
            walk(child, identifier, i)

    root_parent = None
    if task == 'notion-find-job':
        # Upstream duplicates the captured child into the separately created
        # evaluation page before every run. Keep the captured IDs and bytes,
        # but reproduce that resulting hierarchy so the unchanged evaluator
        # can identify the writable copy by its parent.
        root_parent = source['parent_page_id']
        parent = blocks[root_parent]
        guide_bytes = (REPO / 'submodule/Toolathlon/global_preparation/'
                       'how2register_accounts.md').read_bytes()
        assert hashlib.sha256(
            guide_bytes).hexdigest() == source['guide_sha256']
        guide = guide_bytes.decode()
        pattern = (r'create a new page called `([^`]+)` directly under your '
                   r'workspace')
        title = re.search(pattern, guide).group(1)
        title_json = rich([[title]])
        fixture['pages'].append({
            **common(parent), 'parentId':
            None,
            'position':
            0,
            'parentType':
            'workspace',
            'titleText':
            title,
            'propertiesJson': {
                'title': {
                    'id': 'title',
                    'type': 'title',
                    'title': title_json
                }
            },
            'url':
            'https://www.notion.so/' + root_parent.replace('-', '')
        })
        fixture['blocks'].append({
            **common(blocks[root_id]), 'parentId':
            root_parent,
            'position':
            0,
            'type':
            'child_page',
            'payloadJson': {
                'title': plain(blocks[root_id]['properties']['title'])
            },
            'hasChildren':
            bool(blocks[root_id].get('content'))
        })
    walk(root_id, root_parent)
    target = folder / 'rendered/notion' / (task + '.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + '\n')
    (folder.parent / 'notion.json').write_text(
        json.dumps(
            {
                'workspace': task,
                'page_id': root_id,
                'page_title': plain(blocks[root_id]['properties']['title'])
            },
            indent=2) + '\n')
    print(task, len(fixture['pages']), 'pages,', len(fixture['blocks']),
          'blocks')


if __name__ == '__main__':
    for task in ('notion-movies', 'notion-find-job'):
        derive(task)
