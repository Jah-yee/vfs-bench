"""Reproduce fixture trees from recorded public Git commits."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def pinned_repository(record, destination, history=False):
    """Fetch only the recorded revisions into a dedicated bare repository."""
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '--bare', '-q',
                    str(destination)],
                   check=True)
    subprocess.run([
        'git', '-C',
        str(destination), 'config', 'remote.origin.url', record['url']
    ],
                   check=True)
    subprocess.run([
        'git', '-C',
        str(destination), 'config', 'remote.origin.promisor', 'true'
    ],
                   check=True)
    for branch, revision in record['revisions'].items():
        subprocess.run([
            'git', '-C',
            str(destination), 'fetch', '-q', '--filter=blob:limit=4m',
            *([] if history else ['--depth=1']), 'origin',
            f'{revision}:refs/heads/{branch}'
        ],
                       check=True)
    return destination


def reproduce(shared, binary, skip=()):
    """Apply the existing placeholder rule to pinned trees, then publish."""
    sources = json.loads((shared / 'sources.json').read_text())
    with tempfile.TemporaryDirectory(prefix='toolathlon-git-fixture-') as tmp:
        scratch = Path(tmp)
        output = scratch / 'fixtures'
        output.mkdir()
        for index, record in enumerate(sources['repositories']):
            repo = pinned_repository(record, scratch / f'repo-{index}')
            for branch, folder in record['folders'].items():
                revision = record['revisions'][branch]
                tree = subprocess.check_output(
                    ['git', '-C',
                     str(repo), 'ls-tree', '-r', revision],
                    text=True)
                for line in tree.splitlines():
                    info, relative = line.split('\t', 1)
                    if Path(relative).name in skip:
                        continue
                    target = output / folder / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.suffix.lower() in binary:
                        data = f'placeholder for {relative}\n'.encode()
                    else:
                        data = subprocess.check_output([
                            'git', '-C',
                            str(repo), 'cat-file', 'blob',
                            info.split()[2]
                        ])
                    target.write_bytes(data)
        destination = shared / 'fixtures'
        backup = scratch / 'previous'
        if destination.exists():
            shutil.move(destination, backup)
        try:
            shutil.move(output, destination)
        except BaseException:
            if backup.exists():
                shutil.move(backup, destination)
            raise
    return 0
