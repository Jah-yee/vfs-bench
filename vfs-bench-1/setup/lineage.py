"""Verify every DVC lock edge, including frozen directory dependencies."""
import tempfile
from pathlib import Path

import yaml
from dvc.ignore import DvcIgnoreFilter
from dvc_data.hashfile.build import build
from dvc_data.hashfile.db import HashFileDB
from dvc_objects.fs.local import LocalFileSystem

REPO = Path(__file__).resolve().parents[1]


def drift(root=REPO):
    stages = yaml.safe_load((root / 'dvc.lock').read_text())['stages']
    fs = LocalFileSystem()
    ignore = DvcIgnoreFilter(fs, str(root))
    changed = []
    checked = {}
    with tempfile.TemporaryDirectory(prefix='toolathlon-lineage-') as cache:
        odb = HashFileDB(fs, cache)
        for name, stage in stages.items():
            for entry in [*stage.get('deps', []), *stage.get('outs', [])]:
                relative = entry['path']
                if relative not in checked:
                    path = root / relative
                    if not path.exists():
                        checked[relative] = None
                    else:
                        _, _, obj = build(odb,
                                          str(path),
                                          fs,
                                          entry.get('hash', 'md5'),
                                          dry_run=True,
                                          ignore=ignore)
                        checked[relative] = obj.hash_info.value
                if checked[relative] != entry['md5']:
                    changed.append(f'{name}: changed or missing {relative}')
    return changed


def main():
    changed = drift()
    if changed:
        print('\n'.join(changed))
        return 1
    print('All DVC lock edges match, including frozen directories')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
