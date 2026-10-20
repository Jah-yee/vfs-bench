"""Exercise task Python/disk contracts independently of service fixtures."""
import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'agent'))
sys.path.insert(0, str(REPO / 'task'))
import toolathlon  # noqa: E402
import workspace as workspace_backend  # noqa: E402
from workspace import Workspace  # noqa: E402

from server.mcp.mcp_servers import upstream_config  # noqa: E402
from server.seed.papers import close  # noqa: E402

TASKS = tuple(
    sorted(path.parent.parent.name
           for path in (REPO / 'task/toolathlon').glob('*/vfs/workspace.yaml')
           if path.parent.parent.name not in ('arrange-workspace',
                                              'nhl-b2b-analysis')))


def terminal_commands():
    """The command words upstream's terminal allows."""
    terminal = yaml.safe_load(upstream_config('terminal'))
    commands = terminal['params']['env']['ALLOWED_COMMANDS'].split(',')
    return {cmd.strip() for cmd in commands}


def upstream_python(name):
    """Python is exposed by the local executor or the terminal allowlist."""
    if 'python_execute' in toolathlon.needed_local_tools(name):
        return True
    if 'terminal' not in toolathlon.needed_mcp_servers(name):
        return False
    return bool({'python', 'python3'} & terminal_commands())


class Declarations(unittest.TestCase):

    def test_local_native_commands_read_workspace_files(self):
        from mirage.cli.workspace import _resolve_config_arg

        task_config = (REPO / 'task/toolathlon/k8s-redis-helm-upgrade/vfs/'
                       'workspace.yaml')
        node = shutil.which('node')
        self.assertIsNotNone(node)
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp).resolve()
            (work / 'manifest.yaml').write_text('kind: ConfigMap\n')
            (work / 'read.mjs').write_text('''
import { readFileSync } from 'node:fs';
const files = process.argv.slice(2).map(arg =>
  readFileSync(arg.replace(/^--(?:filename|values)=/, ''), 'utf8'));
console.log(JSON.stringify({cwd: process.cwd(), files}));
''')
            env = {
                key: str(work / key)
                for key in re.findall(r'\$\{(\w+)\}', task_config.read_text())
            }
            env.update(AGENT_WORKSPACE=str(work),
                       STACK_DIR=str(work / 'stack'),
                       KUBECTL=node,
                       HELM=node)
            # Test the real task declarations and a config without the
            # redundant workdir hint: confinement owns the process directory.
            # `git` is Mirage's own command rather than a native wrapper, and
            # takes no config.
            native = ('kubectl', 'helm')
            for declared_workdir in (True, False):

                def source(path):
                    body = _resolve_config_arg(path)
                    if not declared_workdir:
                        for name in native:
                            body['clis'][name]['config'].pop('workdir', None)
                    return body

                with (self.subTest(declared_workdir=declared_workdir),
                      patch.dict(os.environ, env),
                      patch('server.shared_workspace.active',
                            return_value=None),
                      patch('mirage.cli.workspace._resolve_config_arg',
                            side_effect=source)):
                    body = workspace_backend.resolved(task_config)
                    for name in native:
                        config = body['clis'][name]['config']
                        self.assertEqual(config['workdir'], str(work))
                        script = '''
import { nativeCommand } from './cli/native.mjs';
const { materialize } = await import(
  './submodule/mirage/typescript/packages/core/dist/io/types.js');
const { NOOPAccessor } = await import(
  './submodule/mirage/typescript/packages/core/dist/accessor/base.js');
let input = ''; for await (const chunk of process.stdin) input += chunk;
const {name, config} = JSON.parse(input);
const [stream, result] = await nativeCommand(name, '').handlers[''].fn(
  new NOOPAccessor(config), [], [], {argv: [
  '/workspace/read.mjs', '--filename=/workspace/manifest.yaml',
  '--values=/workspace/manifest.yaml', 'manifest.yaml']});
process.stdout.write(await materialize(stream));
process.stderr.write(result.stderr);
process.exitCode = result.exitCode;
'''
                        result = subprocess.run(
                            [node, '--input-type=module', '-e', script],
                            cwd=REPO,
                            input=json.dumps({
                                'name': name,
                                'config': config
                            }),
                            capture_output=True,
                            text=True,
                            timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(json.loads(result.stdout), {
                            'cwd': str(work),
                            'files': ['kind: ConfigMap\n'] * 3
                        })

    def test_python_runtime_and_guidance_match_upstream(self):
        for name in TASKS:
            with self.subTest(task=name):
                directory = REPO / 'task/toolathlon' / name / 'vfs'
                config = yaml.safe_load(
                    (directory / 'workspace.yaml').read_text())
                runtimes = [
                    entry['name'] if isinstance(entry, dict) else entry
                    for entry in config['runtimes']
                ]
                expected = upstream_python(name)
                self.assertEqual('pyodide' in runtimes, expected)
                skill = (directory / 'SKILL.md').read_text()
                self.assertEqual('## python3' in skill, expected)
                if expected:
                    self.assertIn(
                        'Python cannot launch subprocesses or make direct '
                        'network requests.', skill)
                    self.assertNotIn('runtimes are unavailable', skill)
                else:
                    self.assertIn('runtimes are unavailable', skill)

    def test_remote_workspace_preserves_declared_python(self):
        from types import SimpleNamespace

        from server.shared_workspace import RemoteWorkspace
        remote = RemoteWorkspace.__new__(RemoteWorkspace)
        remote.box = SimpleNamespace(sandbox_id='test')
        remote.env = {}
        remote.captures = ['python', 'python3', 'git']
        remote.shared_disk = True
        remote.ssh_config = {'host': '127.0.0.1'}
        for name in ('k8s-deployment-cleanup', 'k8s-mysql',
                     'k8s-pr-preview-testing'):
            with self.subTest(task=name), patch.dict(
                    os.environ, E2B_API_KEY='test'), patch(
                        'server.shared_workspace.install_mysql') as install:
                body = yaml.safe_load((REPO / 'task/toolathlon' / name /
                                       'vfs/workspace.yaml').read_text())
                declared = list(body['runtimes'])
                mounted = remote.workspace(body)
                # Only the workspace that declares `mysql` gets the client.
                self.assertEqual(install.called, name == 'k8s-mysql')
                self.assertEqual(mounted['runtimes'][1:], declared)
                self.assertEqual(mounted['runtimes'][0]['captures'], ['git'])
                self.assertNotIn('/work', mounted['mounts'])
                self.assertEqual(
                    mounted['mounts']['/workspace']['config']['root'], '/work')
                self.assertEqual(mounted['env']['HOME'], '/workspace')

    def test_remote_browser_captures_upstream_terminal_commands(self):
        from types import SimpleNamespace

        from server.shared_workspace import BROWSER_CAPTURES, RemoteWorkspace
        name = 'k8s-pr-preview-testing'
        self.assertIn('terminal', toolathlon.needed_mcp_servers(name))
        remote = RemoteWorkspace.__new__(RemoteWorkspace)
        remote.box = SimpleNamespace(sandbox_id='test')
        remote.env = {}
        remote.captures = ['python', 'python3', *BROWSER_CAPTURES]
        remote.shared_disk = True
        remote.ssh_config = {'host': '127.0.0.1'}
        body = yaml.safe_load((REPO / 'task/toolathlon' / name /
                               'vfs/workspace.yaml').read_text())
        with patch.dict(os.environ, E2B_API_KEY='test'):
            captures = remote.workspace(body)['runtimes'][0]['captures']
        # Every native command is one the MCP arm's terminal would run.
        self.assertEqual(captures, list(BROWSER_CAPTURES))
        self.assertLessEqual(set(captures), terminal_commands())


@contextmanager
def owned_daemons():
    """Own both regular and host-initialized daemons, restoring prior state."""
    processes = []
    popen = workspace_backend.subprocess.Popen

    def start(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    with patch.object(workspace_backend, '_RUNNING',
                      None), patch.object(workspace_backend.subprocess,
                                          'Popen',
                                          side_effect=start):
        try:
            yield
        finally:
            for process in reversed(processes):
                close(process)


class Workspaces(unittest.TestCase):

    def test_python_and_shell_share_workspace(self):
        for name in TASKS:
            with (self.subTest(task=name), tempfile.TemporaryDirectory() as
                  tmp, owned_daemons()):
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    port = str(sock.getsockname()[1])
                config = REPO / 'task/toolathlon' / name / 'vfs/workspace.yaml'
                env = {
                    key: 'http://127.0.0.1:1'
                    for key in re.findall(r'\$\{(\w+)\}', config.read_text())
                }
                env.update(
                    AGENT_WORKSPACE=tmp,
                    STACK_DIR=str(Path(tmp) / 'stack'),
                    TOOLATHLON_PYTHON=str(REPO / 'vendor/toolathlon-python'),
                    MIRAGE_DAEMON_PORT=port,
                    DRIVE_FOLDER_ID='f0001',
                    BUSINESS_IMAP_PORT='1143',
                    BUSINESS_SMTP_PORT='1587',
                )
                kubeconfig = Path(tmp) / 'kubeconfig.json'
                kubeconfig.write_text('''{"current-context":"local",
                  "contexts":[{"name":"local","context":{"cluster":"local"}}],
                  "clusters":[{"name":"local","cluster":{"server":"http://127.0.0.1:1"}}],
                  "users":[]}''')
                env['KUBECONFIG'] = str(kubeconfig)
                with patch.dict(os.environ, env):
                    self.assertEqual(toolathlon.shell_cwd(name), '/workspace')
                    resolve = workspace_backend.resolved

                    def runtime_only(path):
                        body = resolve(path)
                        # Remote service reads and mutations have their own
                        # parity cases. This test needs the real disk and
                        # runtime, without initializing unrelated API mounts.
                        body['mounts'] = {
                            key: value
                            for key, value in body['mounts'].items()
                            if key in ('/workspace', '/tmp')
                        }
                        return body

                    with patch.object(workspace_backend,
                                      'resolved',
                                      side_effect=runtime_only):
                        ws = Workspace.create(config)
                    try:
                        self.assertEqual(
                            ws.execute('ls /dev').split(), ['null', 'zero'])
                        self.assertEqual(
                            ws.execute(
                                'echo discard > /dev/null; cat /dev/null'), '')
                        self.assertEqual(
                            ws.execute('head -c 4 /dev/zero | wc -c').strip(),
                            '4')
                        ws.execute('echo tilde > ~/tilde.txt')
                        self.assertEqual((Path(tmp) / 'tilde.txt').read_text(),
                                         'tilde\n')
                        (Path(tmp) / 'host.txt').write_text('host disk')
                        self.assertEqual(ws.execute('cat host.txt'),
                                         'host disk')
                        if not upstream_python(name):
                            self.assertNotEqual(
                                ws.execute_result("python3 -c 'print(1)'")
                                ['exit_code'], 0)
                            continue
                        result = asyncio.run(
                            ws.execute_result_async(
                                """python3 - <<'PYTHON'
import os
from pathlib import Path
import openpyxl, xlsxwriter, PyPDF2, pymupdf, pandas, numpy, pyarrow
import PIL, lxml, docx, pptx, pytesseract, olefile
assert os.getcwd() == '/workspace'
assert os.environ['HOME'] == '/workspace'
assert Path.home() == Path('/workspace')
book = openpyxl.Workbook()
book.active['A1'] = 'disk round trip'
book.save('roundtrip.xlsx')
# As in upstream's image: pytesseract without a tesseract binary, and an
# opencv-python that cannot load.
try:
    pytesseract.get_languages()
except pytesseract.TesseractNotFoundError:
    pass
else:
    raise AssertionError('an OCR engine answered')
try:
    import cv2
except ImportError:
    pass
else:
    raise AssertionError('cv2 imported')
print('RUNTIME_OK')
PYTHON""",
                                cwd=toolathlon.shell_cwd(name)))
                        self.assertEqual(result['exit_code'], 0, result)
                        self.assertIn('RUNTIME_OK', result['stdout'])
                        self.assertTrue(
                            (Path(tmp) / 'roundtrip.xlsx').is_file())
                        if name == 'set-conf-cr-ddl':
                            result = ws.execute_result(
                                "python3 -c 'from datetime import datetime; "
                                "from zoneinfo import ZoneInfo; "
                                "assert datetime(2026, 1, 1, "
                                "tzinfo=ZoneInfo(\"Asia/Hong_Kong\"))"
                                ".utcoffset().total_seconds() == 28800'")
                            self.assertEqual(result['exit_code'], 0, result)
                    finally:
                        ws.close()


if __name__ == '__main__':
    unittest.main()
