"""Install Toolathlon's Kubernetes MCP fork and its locked dependency tree."""
import hashlib
import json
import platform
import subprocess
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VENDOR = REPO / 'vendor/kubernetes-mcp'
VERSION = '1.27.3'


def derive(destination=VENDOR):
    from server.mcp.npm_lock import derive as extract
    extract('mcp-server-kubernetes', destination, 'vfs-bench-kubernetes-mcp')


def main():
    subprocess.run(['npm', 'ci', '--no-audit', '--no-fund'],
                   cwd=VENDOR,
                   check=True)
    system = platform.system().lower()
    arch = {
        'arm64': 'arm64',
        'aarch64': 'arm64',
        'x86_64': 'amd64'
    }[platform.machine()]
    asset = json.loads((REPO / 'server/kubernetes-binaries.json'
                        ).read_text())[f'kubectl-{system}-{arch}']
    url, expected = asset['url'], asset['sha256']
    with urllib.request.urlopen(url) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise ValueError('kubectl checksum does not match the release')
    folder = REPO / 'vendor/kubernetes-bin'
    folder.mkdir(parents=True, exist_ok=True)
    binary = folder / 'kubectl'
    binary.write_bytes(data)
    binary.chmod(0o755)
    (folder / 'source.json'
     ).write_text(json.dumps({
         'url': url,
         'sha256': digest
     }, indent=2) + '\n')
    print(
        f'Installed kubectl {VERSION} and the original Kubernetes MCP server')


if __name__ == '__main__':
    main()
