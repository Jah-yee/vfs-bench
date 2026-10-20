"""Validate source receipts and dependency hashes for the five conversions."""
import ast
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

import yaml

from server.mcp.setup_papers_forms import SOURCES, source_root
from server.seed.kubernetes import original
from task.toolathlon import terminal_output_limits

REPO = Path(__file__).resolve().parents[1]
TASKS = ('canvas-art-manager', 'latex-prompt-box', 'find-alita-paper',
         'woocommerce-customer-survey', 'woocommerce-product-recall')
CLI_CONFIGS = {
    'arxiv-latex': 'arxiv-latex-mcp',
    'arxiv-local': 'arxiv_local',
    'scholarly': 'scholarly_search',
    'google-forms': 'google_forms'
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    terminal = yaml.safe_load(original('configs/mcp_servers/terminal.yaml'))
    source = REPO / ('submodule/toolathlon_gym/local_servers/cli-mcp-server/'
                     'src/cli_mcp_server/server.py')
    config_class = next(
        node for node in ast.parse(source.read_text()).body
        if isinstance(node, ast.ClassDef) and node.name == 'SecurityConfig')
    marker = next(
        ast.literal_eval(node.value) for node in config_class.body
        if isinstance(node, ast.AnnAssign)
        and node.target.id == 'truncate_message')
    env = terminal['params']['env']
    assert terminal_output_limits() == (int(env['MAX_STDOUT_LENGTH']),
                                        int(env['MAX_STDERR_LENGTH']), marker)
    for task in TASKS:
        folder = REPO / 'task/toolathlon' / task
        assert (folder / 'shared/task.md').read_bytes() == original(
            f'tasks/finalpool/{task}/docs/task.md'), task
        workspace = yaml.safe_load((folder / 'vfs/workspace.yaml').read_text())
        for cli, settings in workspace.get('clis', {}).items():
            if cli in CLI_CONFIGS:
                source = yaml.safe_load(
                    original('configs/mcp_servers/' + CLI_CONFIGS[cli] +
                             '.yaml'))
                assert settings['config']['timeoutMs'] == (
                    1000 * source['client_session_timeout_seconds']), cli
        service = 'canvas' if task.startswith('canvas') else 'woocommerce'
        capture = folder / 'shared/fixtures' / service
        if capture.is_dir():
            record = json.loads((capture / 'source.json').read_text())
            for name, expected in record['sha256'].items():
                assert digest((capture / name).read_bytes()) == expected, name
            for name, expected in record['service']['inputs_sha256'].items():
                assert digest(original(name)) == expected, name
    for name, (repo, revision) in SOURCES.items():
        source_root(name)
        folder = REPO / 'vendor' / name
        record = json.loads((folder / 'source.json').read_text())
        assert record['repository'] == 'https://github.com/' + repo
        assert record['commit'] == revision
        assert record['upstream_dockerfile_sha256'] == digest(
            original('Dockerfile'))
        assert revision in original('Dockerfile').decode()
        for file, expected in record['files_sha256'].items():
            assert digest((folder / file).read_bytes()) == expected, file
            source = subprocess.check_output(
                ['git', 'show', revision + ':' + file], cwd=folder / 'src')
            assert source == (folder / file).read_bytes(), (name, file)
    folder = REPO / 'vendor/arxiv-local-mcp'
    record = json.loads((folder / 'source.json').read_text())
    assert digest(original('uv.lock')) == record['upstream_uv_lock_sha256']
    assert (folder / 'original_wrapper.py').read_bytes() == original(
        record['wrapper'])
    lock = tomllib.loads((folder / 'uv.lock').read_text())
    versions = {p['name']: p.get('version') for p in lock['package']}
    for name, version in record['versions'].items():
        assert versions[name] == version, name
    print('Five task sources, service captures and original server locks '
          'match')


if __name__ == '__main__':
    main()
