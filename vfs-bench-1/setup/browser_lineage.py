"""Check original browser sources, capture hashes and dependency lineage."""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from server.mcp.npm_lock import derive
from server.mcp.setup_browser import PACKAGE

REPO = Path(__file__).resolve().parents[1]
TASKS = ('shopping-helper', 'k8s-pr-preview-testing')


def original(path):
    return subprocess.check_output([
        'git', '-C',
        str(REPO / 'submodule/Toolathlon'), 'show', 'HEAD:' + path
    ])


def main():
    for task in TASKS:
        assert (REPO / f'task/toolathlon/{task}/shared/task.md').read_bytes(
        ) == original(f'tasks/finalpool/{task}/docs/task.md'), task
    with tempfile.TemporaryDirectory(prefix='browser-lock-') as directory:
        target = Path(directory)
        derive(PACKAGE, target, 'toolathlon-browser-mcp')
        for name in ('package.json', 'package-lock.json'):
            assert (target /
                    name).read_bytes() == (REPO / 'vendor/browser-mcp' /
                                           name).read_bytes(), name
    for task in ('k8s-pr-preview-testing', 'notion-find-job'):
        folder = REPO / f'task/toolathlon/{task}/shared/fixtures'
        source = json.loads((folder / 'source.json').read_text())
        for path, digest in source['source_sha256'].items():
            assert hashlib.sha256(original(path)).hexdigest() == digest, path
        for path, digest in source['sha256'].items():
            assert hashlib.sha256(
                (folder / path).read_bytes()).hexdigest() == digest, path
        if task == 'k8s-pr-preview-testing':
            heads = subprocess.check_output([
                'git', 'bundle', 'list-heads',
                str(folder / 'repository.bundle')
            ],
                                            text=True)
            assert heads.strip(
            ) == source['revision'] + ' refs/heads/' + source['branch']
        else:
            assert hashlib.sha256(
                original('global_preparation/how2register_accounts.md')
            ).hexdigest() == source['guide_sha256']
    folder = REPO / 'task/toolathlon/gdp-cr5-analysis/shared/fixtures/sheets'
    source = json.loads((folder / 'source.json').read_text())
    assert hashlib.sha256(original(
        source['source'])).hexdigest() == source['source_sha256']
    assert hashlib.sha256(
        (folder / 'source.xlsx').read_bytes()).hexdigest() == source['sha256']
    print(
        'Original browser task prompts, source captures and npm closure match')


if __name__ == '__main__':
    main()
