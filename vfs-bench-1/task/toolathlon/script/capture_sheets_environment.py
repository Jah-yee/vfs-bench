"""Freeze the existing upstream Sheets launcher's dependency tree."""
import hashlib
import json
import subprocess
from pathlib import Path

from server.seed.kubernetes import original

REPO = Path(__file__).resolve().parents[3]
DEST = REPO / 'vendor/google-sheets-mcp'


def publish(packages):
    DEST.mkdir(parents=True, exist_ok=True)
    deps = [f'{name}=={version}' for name, version in sorted(packages.items())]
    manifest = ('[project]\nname = "vfs-bench-google-sheets-mcp"\n'
                'version = "0.0.0"\nrequires-python = ">=3.12"\n'
                'dependencies = [\n' + ',\n'.join('    ' + json.dumps(dep)
                                                  for dep in deps) + '\n]\n')
    (DEST / 'pyproject.toml').write_text(manifest)
    source = 'configs/mcp_servers/google_sheet.yaml'
    (DEST / 'source.json').write_text(
        json.dumps(
            {
                'upstream_config':
                source,
                'upstream_config_sha256':
                hashlib.sha256(original(source)).hexdigest(),
                'divergence':
                'Upstream has no package version. Freeze the existing '
                'launcher resolution, including its MCP<2 '
                'compatibility constraint.',
                'packages':
                packages,
            },
            indent=2) + '\n')


def main():
    data = subprocess.check_output([
        'uvx',
        '--with',
        'mcp>=1.2,<2',
        '--from',
        'mcp-google-sheets',
        'python',
        '-c',
        'import importlib.metadata as m,json; '
        'print(json.dumps({d.metadata["Name"]:d.version '
        'for d in m.distributions()}))',
    ],
                                   text=True)
    publish(json.loads(data))
    subprocess.run(['uv', 'lock', '--directory', str(DEST)], check=True)


if __name__ == '__main__':
    main()
