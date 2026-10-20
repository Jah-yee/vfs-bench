"""Install original Maps, railway and video servers with full source locks."""
import hashlib
import json
import subprocess
from pathlib import Path

from server.seed.kubernetes import original

REPO = Path(__file__).resolve().parents[2]
SOURCES = {
    'youtube-mcp': ('lockon-n/youtube-mcp-server',
                    'b202e00e9014bf74b9f5188b623cad16f13c01c4'),
    'youtube-transcript-mcp': ('jkawamoto/mcp-youtube-transcript',
                               '28081729905a48bef533d864efbd867a2bfd14cd'),
}
PACKAGES = {
    'maps-mcp': '@modelcontextprotocol/server-google-maps',
    'rail-mcp': '12306-mcp@0.3.9',
}


def source_root(name):
    root = REPO / 'vendor' / name
    receipt = json.loads((root / 'source.json').read_text())
    source = root / 'src' if name in SOURCES else root
    if name in SOURCES:
        head = subprocess.check_output(
            ['git', '-C', str(source), 'rev-parse', 'HEAD'],
            text=True).strip()
        dirty = subprocess.run(
            ['git', '-C', str(source), 'diff', '--quiet', 'HEAD']).returncode
        if head != SOURCES[name][1] or dirty:
            raise ValueError(name + ' source differs from original pin')
    for file, digest in receipt['files_sha256'].items():
        if hashlib.sha256((root / file).read_bytes()).hexdigest() != digest:
            raise ValueError(name + ' dependency receipt changed')
        if (source / file).read_bytes() != (root / file).read_bytes():
            raise ValueError(name + ' installed dependency lock changed')
    return source


def install():
    for name, (repository, revision) in SOURCES.items():
        docker = original('Dockerfile')
        assert repository.encode() in docker and revision.encode() in docker
        root = REPO / 'vendor' / name
        source = root / 'src'
        root.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            subprocess.run([
                'git', 'clone', '--quiet', 'https://github.com/' + repository,
                str(source)
            ],
                           check=True)
        subprocess.run([
            'git', '-C',
            str(source), 'checkout', '--quiet', '--detach', revision
        ],
                       check=True)
        files = ['pyproject.toml', 'uv.lock'] if 'transcript' in name else [
            'package.json', 'package-lock.json'
        ]
        for file in files:
            shown = subprocess.run(
                ['git', '-C', str(source), 'show', 'HEAD:' + file],
                capture_output=True)
            if shown.returncode and file == 'package-lock.json':
                if (root / file).exists():
                    (source / file).write_bytes((root / file).read_bytes())
                else:
                    subprocess.run([
                        'npm', 'install', '--package-lock-only',
                        '--ignore-scripts', '--no-audit', '--no-fund'
                    ],
                                   cwd=source,
                                   check=True)
                data = (source / file).read_bytes()
            else:
                shown.check_returncode()
                data = shown.stdout
            if (root / file).exists() and (root / file).read_bytes() != data:
                raise ValueError('Committed lock differs from original: ' +
                                 file)
            (root / file).write_bytes(data)
        receipt = {
            'repository': 'https://github.com/' + repository,
            'commit': revision,
            'upstream_dockerfile_sha256': hashlib.sha256(docker).hexdigest(),
            'files_sha256': {
                file: hashlib.sha256((root / file).read_bytes()).hexdigest()
                for file in files
            }
        }
        (root / 'source.json').write_text(json.dumps(receipt, indent=2) + '\n')
        source_root(name)
        if 'transcript' in name:
            subprocess.run(['uv', 'sync', '--locked', '--python', '3.12'],
                           cwd=source,
                           check=True)
        else:
            subprocess.run(
                ['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'],
                cwd=source,
                check=True)
            subprocess.run(['npm', 'run', 'build'], cwd=source, check=True)
    for name, package in PACKAGES.items():
        root = REPO / 'vendor' / name
        root.mkdir(parents=True, exist_ok=True)
        if name == 'maps-mcp':
            from server.mcp.npm_lock import derive
            derive(package, root, 'vfs-bench-' + name)
        if not (root / 'package-lock.json').exists():
            (root / 'package.json').write_text(
                json.dumps({
                    'name': 'vfs-bench-' + name,
                    'private': True
                }) + '\n')
            subprocess.run([
                'npm', 'install', '--save-exact', '--ignore-scripts',
                '--no-audit', '--no-fund', package
            ],
                           cwd=root,
                           check=True)
        else:
            subprocess.run(
                ['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'],
                cwd=root,
                check=True)
        config = 'google_map' if name == 'maps-mcp' else '12306'
        receipt = {
            'upstream_config':
            'configs/mcp_servers/' + config + '.yaml',
            'upstream_config_sha256':
            hashlib.sha256(original('configs/mcp_servers/' + config +
                                    '.yaml')).hexdigest(),
            'files_sha256': {
                file: hashlib.sha256((root / file).read_bytes()).hexdigest()
                for file in ('package.json', 'package-lock.json')
            }
        }
        if name == 'maps-mcp':
            receipt['upstream_package_lock_sha256'] = hashlib.sha256(
                original('package-lock.json')).hexdigest()
        (root / 'source.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    install()
