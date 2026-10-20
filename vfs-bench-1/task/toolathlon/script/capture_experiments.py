"""Capture Guru, pinning large public files by source checksum."""
import base64
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import requests

from server.seed.kubernetes import original
from task.toolathlon.script.capture_wandb import (DEST, FILES, HISTORY,
                                                  PROJECT, REPO, RUNS,
                                                  capture_windows,
                                                  check_snapshot, pages, query)


def capture_project(destination):
    """Keep the existing inline-file capture producer immutable."""
    entity, project = 'mbzuai-llm', 'Guru'
    variables = {'entity': entity, 'project': project}
    with requests.Session() as session:
        session.trust_env = False
        metadata = query(session, PROJECT, variables)['project']
        runs = pages(session, RUNS, variables, ('project', 'runs'))
        if len(runs) != metadata['runCount']:
            raise ValueError('Guru run inventory changed during capture')
        for run in runs:
            at = {**variables, 'run': run['name']}
            for key in ('config', 'summaryMetrics', 'systemMetrics'):
                if isinstance(run[key], str):
                    run[key] = json.loads(run[key])
            if run['sweepName']:
                raise ValueError('Capture the referenced sweep first')
            last = run['historyKeys']['lastStep']
            history = []
            for start in range(0, last + 1, 100):
                stop = min(start + 100, last + 1)
                rows = query(
                    session, HISTORY, {
                        **at, 'start':
                        max(0, start - 1) if stop - start == 1 else start,
                        'stop': max(stop, 2),
                        'samples': 100
                    })['project']['run']['history']
                history.extend(
                    row for text in rows
                    if start <= (row := json.loads(text))['_step'] < stop)
            if (len(history) != run['historyLineCount']
                    or len({row['_step']
                            for row in history}) != len(history)):
                raise ValueError('Incomplete or duplicated Guru history')
            run['history'] = history
            run['historySamples'] = []
            for args in ({}, {'samples': 500}, {'samples': 1000}):
                arguments = '' if not args else f"(samples:{args['samples']})"
                text = (
                    'query($entity:String!,$project:String!,$run:String!){'
                    'project(entityName:$entity,name:$project){run(name:$run){'
                    'history' + arguments + '}}}')
                rows = query(session, text, at)['project']['run']['history']
                run['historySamples'].append({'args': args, 'rows': rows})
            files = pages(session, FILES, at, ('project', 'run', 'files'))
            run['capturedFileCount'] = len(files)
            run['files'] = {}
            for file in files:
                record = {
                    'sourceId': file['id'],
                    'mimetype': file['mimetype'],
                    'updatedAt': file['updatedAt'],
                    'sourceSizeBytes': file['sizeBytes'],
                    'sourceMd5': file['md5']
                }
                if file['md5']:
                    record['remote'] = {**at, 'name': file['name']}
                else:
                    response = session.get(file['directUrl'], timeout=120)
                    response.raise_for_status()
                    record['base64'] = base64.b64encode(
                        response.content).decode()
                run['files'][file['name']] = record
            print(run['name'],
                  len(history),
                  'history rows,',
                  len(files),
                  'files',
                  flush=True)
    # Match the fixture authentication identity used by the existing capture.
    fixture = {
        'source': {
            'url': f'https://wandb.ai/{entity}/{project}',
            'captured_at': datetime.now(timezone.utc).isoformat(),
            'queries': {
                'project': PROJECT,
                'runs': RUNS,
                'history': HISTORY,
                'files': FILES
            }
        },
        'entities': {
            entity: {
                project: runs
            }
        },
        'projects': {
            f'{entity}/{project}': {
                **metadata, 'sweeps': {}
            }
        },
        'viewer': {
            'id': 'fixture',
            'name': 'fixture',
            'username': 'fixture',
            'entity': entity,
            'email': None,
            'admin': False,
            'flags': '{}',
            'teams': {
                'edges': [{
                    'node': {
                        'name': entity
                    }
                }]
            }
        },
    }
    path = destination / 'Guru.json'
    path.write_text(json.dumps(fixture, separators=(',', ':')) + '\n')
    return path


def main():
    task_path = 'tasks/finalpool/experiments-recordings/docs/task.md'
    task = original(task_path)
    if b'mbzuai-llm/Guru' not in task:
        raise ValueError('The original experiments project changed')
    target = DEST / 'Guru.json.gz'
    if target.exists():
        raise FileExistsError('The original Guru capture already exists')
    with TemporaryDirectory(dir=DEST) as directory:
        path = capture_project(Path(directory))
        capture_windows(path)
        fixture = json.loads(path.read_text())
        check_snapshot(fixture)
        fixture['source']['task_sha256'] = {
            task_path: hashlib.sha256(task).hexdigest()
        }
        fixture['source']['capture_sha256'] = {
            str(p.relative_to(REPO)):
            hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__).resolve(),
                      REPO / 'task/toolathlon/script/capture_wandb.py',
                      REPO / 'uv.lock')
        }
        fixture['source']['file_content'] = (
            'Public files are fetched on demand. Their source MD5 and byte '
            'length must match this capture before any bytes are returned.')
        packed = path.with_suffix('.json.gz')
        packed.write_bytes(
            gzip.compress(
                (json.dumps(fixture, separators=(',', ':')) + '\n').encode(),
                mtime=0))
        packed.replace(target)
    print(target)


if __name__ == '__main__':
    main()
