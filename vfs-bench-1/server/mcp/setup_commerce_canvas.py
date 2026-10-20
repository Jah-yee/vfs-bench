"""Install the original Canvas and WooCommerce servers and dependency trees."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from server.mcp.npm_lock import derive as extract

REPO = Path(__file__).resolve().parents[2]
PACKAGES = {
    'canvas': 'canvas-mcp-server',
    'woocommerce': '@lockon0927/woocommerce-mcp'
}


def capture():
    """Copy pinned tools and fingerprint their implementations."""
    from server.mcp.mcp_servers import upstream_config
    for kind, package in PACKAGES.items():
        folder = REPO / f'vendor/{kind}-mcp'
        entry = folder / 'node_modules' / package / (
            'build/index.js' if kind == 'canvas' else 'dist/index.js')
        tools = folder / 'tools.json'
        code = ('const [entry,destination] = process.argv.slice(1); '
                'const {loadOriginal} = await import(' + json.dumps(
                    (REPO / 'server/clients/original_tools.mjs').as_uri()) +
                '); const h = await loadOriginal(entry); '
                'const t = await h.get("tools/list")({method:"tools/list"}); '
                'const {writeFileSync} = await import("node:fs"); '
                'writeFileSync(destination, JSON.stringify(t,null,2)+"\\n");')
        with tempfile.TemporaryDirectory() as cwd:
            subprocess.run(
                [
                    'node', '--input-type=module', '-e', code,
                    str(entry),
                    str(tools)
                ],
                cwd=cwd,
                check=True,
                timeout=60,
                env={
                    'PATH': os.environ['PATH'],
                    'CANVAS_API_TOKEN': 'fixture',
                    'CANVAS_DOMAIN': 'example.invalid',
                    'WORDPRESS_SITE_URL': 'https://example.invalid',
                    'WOOCOMMERCE_CONSUMER_KEY': 'fixture',
                    'WOOCOMMERCE_CONSUMER_SECRET': 'fixture',
                })
        paths = sorted(p for p in entry.parent.rglob('*')
                       if p.is_file() and p.suffix == '.js')
        record = {
            'upstream_config':
            f'configs/mcp_servers/{kind}.yaml',
            'upstream_config_sha256':
            hashlib.sha256(upstream_config(kind).encode()).hexdigest(),
            'sha256': {
                str(p.relative_to(folder)):
                hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [
                    folder / 'package.json', folder /
                    'package-lock.json', tools, *paths
                ]
            },
        }
        (folder /
         'source.json').write_text(json.dumps(record, indent=2) + '\n')


def verify(kind):
    """Refuse changed installed tool code or schemas before either arm runs."""
    from server.mcp.mcp_servers import upstream_config
    folder = REPO / f'vendor/{kind}-mcp'
    record = json.loads((folder / 'source.json').read_text())
    if hashlib.sha256(upstream_config(
            kind).encode()).hexdigest() != record['upstream_config_sha256']:
        raise ValueError(
            f'{kind} upstream config differs from its tool capture')
    for name, digest in record['sha256'].items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'{kind} tool source changed: {name}')


def derive():
    for name, package in PACKAGES.items():
        extract(package, REPO / f'vendor/{name}-mcp', f'vfs-bench-{name}-mcp')


def main():
    for name, package in PACKAGES.items():
        folder = REPO / f'vendor/{name}-mcp'
        subprocess.run(['npm', 'ci', '--no-audit', '--no-fund'],
                       cwd=folder,
                       check=True)
        metadata = json.loads(
            (folder / 'node_modules' / package / 'package.json').read_text())
        print(name, metadata['version'], metadata.get('bin'))
    capture()


if __name__ == '__main__':
    main()
