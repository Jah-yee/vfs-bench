"""Capture and verify the pinned emails-mcp handlers exposed by the CLI."""
import asyncio
import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
VENDOR = REPO / 'vendor/emails-mcp'


async def _tools(app):
    from mcp import types
    from mcp.server.lowlevel.server import request_ctx

    original = app._mcp_server
    async with original.lifespan(original) as context:
        request = types.ListToolsRequest(method='tools/list')
        token = request_ctx.set(
            SimpleNamespace(request_id=0,
                            meta=None,
                            session=None,
                            lifespan_context=context))
        try:
            result = await original.request_handlers[type(request)](request)
            return result.root.model_dump(mode='json', exclude_none=True)
        finally:
            request_ctx.reset(token)


def installed_sources():
    """Return emails-mcp's installed Python sources under stable names."""
    found = list(
        (VENDOR / '.venv').glob('lib/python*/site-packages/emails_mcp'))
    if len(found) != 1:
        raise FileNotFoundError('Install the locked emails-mcp project')
    package = found[0]
    return {
        str(path.relative_to(package.parent)):
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(package.rglob('*.py'))
    }


def installed_version():
    """Read the installed distribution version without importing it."""
    found = list(
        (VENDOR / '.venv'
         ).glob('lib/python*/site-packages/emails_mcp-*.dist-info/METADATA'))
    if len(found) != 1:
        raise FileNotFoundError('Install the locked emails-mcp project')
    for line in found[0].read_text().splitlines():
        if line.startswith('Version: '):
            return line.removeprefix('Version: ')
    raise ValueError('emails-mcp installation has no version metadata')


def capture():
    """Record exact schemas and source fingerprints from the locked project."""
    from server.clients.original_tools import emails_app
    from server.mcp.mcp_servers import upstream_config

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        config = root / 'emails.json'
        config.write_text(
            json.dumps({
                'email': 'capture@example.invalid',
                'password': 'capture',
                'use_ssl': False,
                'use_starttls': False,
            }))
        app, cleanup = emails_app([
            '--attachment_upload_path', directory,
            '--attachment_download_path',
            str(root / 'downloads'), '--email_export_path',
            str(root / 'exports'), '--config_file',
            str(config)
        ])
        try:
            tools = asyncio.run(_tools(app))
        finally:
            cleanup()

    encoded = (json.dumps(tools, indent=2) + '\n').encode()
    (VENDOR / 'tools.json').write_bytes(encoded)
    record = {
        'package':
        'emails-mcp',
        'version':
        installed_version(),
        'upstream_config':
        'configs/mcp_servers/emails.yaml',
        'upstream_config_sha256':
        hashlib.sha256(upstream_config('emails').encode()).hexdigest(),
        'lock_sha256':
        hashlib.sha256((VENDOR / 'uv.lock').read_bytes()).hexdigest(),
        'tools_sha256':
        hashlib.sha256(encoded).hexdigest(),
        'source_sha256':
        installed_sources(),
    }
    (VENDOR / 'source.json').write_text(json.dumps(record, indent=2) + '\n')


def verify():
    """Refuse schema, package, lock, config, or installed-source drift."""
    from server.mcp.mcp_servers import upstream_config

    record = json.loads((VENDOR / 'source.json').read_text())
    checks = {
        'version':
        installed_version(),
        'upstream_config_sha256':
        hashlib.sha256(upstream_config('emails').encode()).hexdigest(),
        'lock_sha256':
        hashlib.sha256((VENDOR / 'uv.lock').read_bytes()).hexdigest(),
        'tools_sha256':
        hashlib.sha256((VENDOR / 'tools.json').read_bytes()).hexdigest(),
        'source_sha256':
        installed_sources(),
    }
    for name, value in checks.items():
        if value != record[name]:
            raise ValueError('emails-mcp ' + name.replace('_', ' ') +
                             ' differs from its capture')


if __name__ == '__main__':
    capture()
