"""Install locked original MCP servers used by remote seeders and graders."""
import hashlib
import shlex
from pathlib import Path

import yaml

from server.seed.kubernetes import command, original

REPO = Path(__file__).resolve().parents[2]


def prepare(box, service):
    config_path = f'configs/mcp_servers/{service}.yaml'
    source = original(config_path)
    config = yaml.safe_load(source)
    folder = f'/opt/fixture-mcp/{service}'
    vendor = REPO / f'vendor/{service}-mcp'
    files = ['package.json', 'package-lock.json'
             ] if service == 'canvas' else ['pyproject.toml', 'uv.lock']
    hashes = {}
    for name in files:
        data = (vendor / name).read_bytes()
        box.files.write(folder + '/' + name, data, user='root')
        hashes[name] = hashlib.sha256(data).hexdigest()
    params = config['params']
    if service == 'canvas':
        command(box,
                'cd ' + shlex.quote(folder) +
                ' && sudo npm ci --no-audit --no-fund',
                timeout=180)
        params['command'] = 'node'
        params['args'] = [
            folder + '/node_modules/canvas-mcp-server/build/index.js'
        ]
    elif service == 'emails':
        command(box,
                'sudo uv sync --locked --project ' + shlex.quote(folder),
                timeout=180)
        params['command'] = 'uv'
        params['args'] = [
            'run', '--locked', '--project', folder, *params['args']
        ]
    else:
        raise ValueError('Unsupported remote MCP fixture server: ' + service)
    rendered = yaml.safe_dump(config, sort_keys=False).encode()
    box.files.write('/opt/toolathlon/' + config_path, rendered, user='root')
    return {
        'source': config_path,
        'source_sha256': hashlib.sha256(source).hexdigest(),
        'lock_sha256': hashes,
        'launch_sha256': hashlib.sha256(rendered).hexdigest(),
    }
