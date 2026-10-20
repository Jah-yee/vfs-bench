"""Restore the public Notion source beside the captured W&B project."""
import json
import os
import selectors
import subprocess
from contextlib import contextmanager
from pathlib import Path

from server.clients import notion

REPO = Path(__file__).resolve().parents[2]


@contextmanager
def serve(task_dir):
    from server.fakes.wandb_api import serve as wandb
    config = json.loads((task_dir / 'shared/notion.json').read_text())
    fixture_root = task_dir / 'shared/fixtures/notion/rendered'
    integ = REPO / 'submodule/mirage/integ'
    previous = {
        key: os.environ.get(key)
        for key in ('NOTION_URL', 'NOTION_TOKEN')
    }
    process = subprocess.Popen([
        str(integ / 'node_modules/.bin/tsx'),
        str(REPO / 'server/fakes/notion_api.mjs'), '--port', '0', '--fixture',
        'experiments-recordings', '--fixture-root',
        str(fixture_root)
    ],
                               cwd=integ,
                               stdout=subprocess.PIPE,
                               text=True)
    token_file = (REPO / 'submodule/Toolathlon/tasks/finalpool' /
                  'experiments-recordings/files/duplicated_page_id.txt')
    old_id = token_file.read_bytes() if token_file.exists() else None
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=30):
                raise RuntimeError('Notion fixture did not start')
            line = process.stdout.readline().strip()
        if not line.startswith('NOTION_URL=http://127.0.0.1:'):
            raise RuntimeError(
                'Notion fixture did not announce its endpoint: ' + line)
        os.environ.update(NOTION_URL=line.split('=', 1)[1],
                          NOTION_TOKEN=config['workspace'])
        notion.reset(config['workspace'], 'experiments-recordings')
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(config['page_id'])
        with wandb(task_dir) as base:
            yield base
    finally:
        if old_id is None:
            token_file.unlink(missing_ok=True)
        else:
            token_file.write_bytes(old_id)
        from server.seed.papers import close
        close(process)
        process.stdout.close()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
