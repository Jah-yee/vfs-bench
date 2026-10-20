"""Validate original task declarations, server locks and public captures."""
import hashlib
import json
import tempfile
import tomllib
from pathlib import Path

import yaml

from server.mcp.mcp_servers import (SERVERS, TIMEOUT_CONFIG, timeout_for,
                                    upstream_config)
from server.mcp.npm_lock import derive
from server.mcp.setup_travel_video import SOURCES, source_root
from server.seed.final_batch import TASKS
from server.seed.kubernetes import original
from setup.final_tasks import CLI_NAMES

REPO = Path(__file__).resolve().parents[1]


def main():
    # Verified against server.py in lockon-n/yahoo-finance-mcp at the commit
    # selected by Toolathlon's Dockerfile; Gym carries those identical bytes.
    yahoo_commit = '469103ba1464486cb7b8bd2c1f6355f42ca64a5b'
    assert yahoo_commit.encode() in original('Dockerfile')
    yahoo = (REPO / 'submodule/toolathlon_gym/local_servers/'
             'yahoo-finance-mcp/server.py')
    assert hashlib.sha256(yahoo.read_bytes()).hexdigest() == (
        'aec532b300aa5309b6b2219b8fe0ccf17c6c96554ab7308b9071ff0dcff71c62')
    for task in TASKS:
        root = REPO / 'task/toolathlon' / task
        prefix = f'tasks/finalpool/{task}/'
        assert (root /
                'shared/task.md').read_bytes() == original(prefix +
                                                           'docs/task.md')
        config = json.loads(original(prefix + 'task_config.json'))
        workspace = yaml.safe_load((root / 'vfs/workspace.yaml').read_text())
        for name in config['needed_mcp_servers']:
            assert name in SERVERS, (task, name)
            upstream = yaml.safe_load(
                upstream_config(TIMEOUT_CONFIG.get(name, name)))
            assert timeout_for(name) == upstream.get(
                'client_session_timeout_seconds')
            if name in CLI_NAMES:
                cli = workspace['clis'][CLI_NAMES[name][0]]
                assert cli['config']['timeoutMs'] == 1000 * timeout_for(name)
        assert ('web-search'
                in workspace['clis']) == ('web_search'
                                          in config['needed_local_tools'])
        assert ('browser'
                in workspace['clis']) == ('playwright_with_chunk'
                                          in config['needed_mcp_servers'])
        capture = root / 'shared/fixtures/source.json'
        if capture.exists():
            record = json.loads(capture.read_text())
            for path, digest in record['source_sha256'].items():
                assert hashlib.sha256(original(path)).hexdigest() == digest
            for path, digest in record['sha256'].items():
                assert hashlib.sha256(
                    (capture.parent / path).read_bytes()).hexdigest() == digest
    for name in SOURCES:
        source_root(name)
    source_root('maps-mcp')
    source_root('rail-mcp')
    for name, package in [
        ('filesystem-mcp', '@modelcontextprotocol/server-filesystem'),
        ('maps-mcp', '@modelcontextprotocol/server-google-maps'),
        ('memory-mcp', '@modelcontextprotocol/server-memory')
    ]:
        with tempfile.TemporaryDirectory() as directory:
            derive(package, Path(directory), 'vfs-bench-' + name)
            for file in ('package.json', 'package-lock.json'):
                assert (REPO / 'vendor' / name /
                        file).read_bytes() == (Path(directory) /
                                               file).read_bytes()
    toolathlon_lock = tomllib.loads(original('uv.lock').decode())
    excel = next(package for package in toolathlon_lock['package']
                 if package['name'] == 'excel-mcp-server')
    assert excel['version'] == '0.1.4'
    assert (json.loads(original('package-lock.json'))['packages']
            ['node_modules/@modelcontextprotocol/server-filesystem']['version']
            == '2025.7.1')
    print('16 original task declarations, service mappings, captures and '
          'locked servers match')


if __name__ == '__main__':
    main()
