"""Install Toolathlon's pinned paper and Forms servers."""
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

from server.seed.kubernetes import original

REPO = Path(__file__).resolve().parents[2]
SOURCES = {
    'arxiv-latex-mcp': ('takashiishida/arxiv-latex-mcp',
                        'f8bd3b3b6d3d066fe29ba356023a0b3e8215da43'),
    'scholarly-mcp':
    ('lockon-n/mcp-scholarly', '82a6ca268ae0d2e10664be396e1a0ea7aba23229'),
    'forms-mcp': ('matteoantoci/google-forms-mcp',
                  '96f7fa1ff02b8130105ddc6d98796f3b49c1c574'),
}


def checkout(name):
    repo, commit = SOURCES[name]
    dockerfile = original('Dockerfile').decode()
    assert repo in dockerfile and commit in dockerfile
    root = REPO / 'vendor' / name
    source = root / 'src'
    if not (source / '.git').exists():
        subprocess.run([
            'git', 'clone', '--quiet', 'https://github.com/' + repo,
            str(source)
        ],
                       check=True)
    subprocess.run(['git', 'checkout', '--quiet', '--detach', commit],
                   cwd=source,
                   check=True)
    return root, source


def source_root(name):
    """Refuse a moved or patched foreign server tree before either arm runs."""
    root = REPO / 'vendor' / name
    if name == 'arxiv-local-mcp':
        path = 'utils/local_servers/arxiv_local_wrapper.py'
        if (root / 'original_wrapper.py').read_bytes() != original(path):
            raise ValueError('Original arxiv wrapper has drifted')
        return root
    source = root / 'src'
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                   cwd=source,
                                   text=True).strip()
    dirty = subprocess.run(['git', 'diff', '--quiet', 'HEAD'],
                           cwd=source).returncode
    if head != SOURCES[name][1] or dirty:
        raise ValueError(name + ' source tree differs from its original pin')
    files = ('package.json', 'package-lock.json') if name == 'forms-mcp' else (
        'pyproject.toml', 'uv.lock')
    for file in files:
        if (source / file).read_bytes() != (root / file).read_bytes():
            raise ValueError(name +
                             ' dependency lock differs from its receipt')
    return source


def derive():
    for name in SOURCES:
        root, source = checkout(name)
        names = ('package.json',
                 'package-lock.json') if name == 'forms-mcp' else (
                     'pyproject.toml', 'uv.lock')
        for filename in names:
            data = subprocess.check_output(['git', 'show', 'HEAD:' + filename],
                                           cwd=source)
            (root / filename).write_bytes(data)
        receipt = {
            'repository':
            'https://github.com/' + SOURCES[name][0],
            'commit':
            SOURCES[name][1],
            'upstream_dockerfile_sha256':
            hashlib.sha256(original('Dockerfile')).hexdigest(),
            'files_sha256': {
                filename:
                hashlib.sha256((root / filename).read_bytes()).hexdigest()
                for filename in names
            },
        }
        (root / 'source.json').write_text(json.dumps(receipt, indent=2) + '\n')
    root = REPO / 'vendor/arxiv-local-mcp'
    root.mkdir(exist_ok=True)
    lock = tomllib.loads(original('uv.lock').decode())
    packages = {p['name']: p for p in lock['package']}
    required = {'arxiv-mcp-server'}
    pending = list(required)
    while pending:
        for dep in packages[pending.pop()].get('dependencies', []):
            if dep['name'] not in required:
                required.add(dep['name'])
                pending.append(dep['name'])
    manifest = ('[project]\nname = "vfs-bench-arxiv-local-mcp"\n'
                'version = "0.0.0"\nrequires-python = ">=3.12"\n'
                'dependencies = [\n')
    manifest += ''.join(
        '    ' + json.dumps(name + '==' + packages[name]['version']) + ',\n'
        for name in sorted(required)) + ']\n'
    (root / 'pyproject.toml').write_text(manifest)
    wrapper = 'utils/local_servers/arxiv_local_wrapper.py'
    (root / 'original_wrapper.py').write_bytes(original(wrapper))
    (root / 'source.json').write_text(
        json.dumps(
            {
                'upstream_uv_lock_sha256':
                hashlib.sha256(original('uv.lock')).hexdigest(),
                'wrapper':
                wrapper,
                'wrapper_sha256':
                hashlib.sha256(original(wrapper)).hexdigest(),
                'versions': {
                    name: packages[name]['version']
                    for name in sorted(required)
                },
            },
            indent=2) + '\n')


def install():
    for name in SOURCES:
        root, source = checkout(name)
        source_root(name)
        names = ('package.json',
                 'package-lock.json') if name == 'forms-mcp' else (
                     'pyproject.toml', 'uv.lock')
        for filename in names:
            assert (source /
                    filename).read_bytes() == (root /
                                               filename).read_bytes(), filename
        if name == 'forms-mcp':
            subprocess.run(['npm', 'ci', '--no-audit', '--no-fund'],
                           cwd=source,
                           check=True)
            subprocess.run(['npm', 'run', 'build'], cwd=source, check=True)
        else:
            subprocess.run(['uv', 'sync', '--locked', '--python', '3.12'],
                           cwd=source,
                           check=True)
    subprocess.run(['uv', 'sync', '--locked', '--python', '3.12'],
                   cwd=REPO / 'vendor/arxiv-local-mcp',
                   check=True)


if __name__ == '__main__':
    install()
