"""Extract a server dependency closure from Toolathlon's npm lock."""
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def installed_version(installed: Path) -> str | None:
    """Return the installed version, or None when nothing is installed.

    Args:
        installed (Path): the installed package's directory.

    Returns:
        str | None: the version string in the installed package.json.
    """
    manifest = installed / "package.json"
    if not manifest.is_file():
        return None
    try:
        return str(json.loads(manifest.read_text()).get("version"))
    except json.JSONDecodeError:
        return None


def derive(package: str, destination: Path, label: str):
    source = json.loads(
        subprocess.check_output([
            'git', '-C',
            str(REPO / 'submodule/Toolathlon'), 'show',
            'HEAD:package-lock.json'
        ]))
    packages = source['packages']
    spec = packages['']['dependencies'][package]
    picked = {}

    def locate(parent, name):
        while True:
            prefix = parent + '/' if parent else ''
            path = prefix + 'node_modules/' + name
            if path in packages:
                return path
            if not parent:
                return None
            parent = parent.rsplit('/node_modules/',
                                   1)[0] if '/node_modules/' in parent else ''

    def visit(path):
        if path in picked:
            return
        entry = packages[path]
        picked[path] = entry
        for kind in ('dependencies', 'optionalDependencies',
                     'peerDependencies'):
            for name in entry.get(kind, {}):
                found = locate(path, name)
                if found:
                    visit(found)
                elif kind == 'dependencies':
                    raise ValueError(
                        f'Missing upstream dependency {path}: {name}')

    visit('node_modules/' + package)
    manifest = {
        'name': label,
        'private': True,
        'dependencies': {
            package: spec
        }
    }
    lock = {
        'name': manifest['name'],
        'lockfileVersion': 3,
        'requires': True,
        'packages': {
            '': {
                'name': manifest['name'],
                'dependencies': manifest['dependencies']
            },
            **dict(sorted(picked.items()))
        }
    }
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in [('package.json', manifest),
                          ('package-lock.json', lock)]:
        (destination / name).write_text(json.dumps(content, indent=2) + '\n')
