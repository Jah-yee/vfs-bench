"""Executable regressions for the Round 3 audit repairs."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

REPO = Path(__file__).resolve().parents[1]
for folder in ('agent', 'cli', 'task', '.'):
    sys.path.insert(0, str(REPO / folder))

import dataset  # noqa: E402
import toolathlon  # noqa: E402


class Round3(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        dataset.use('toolathlon')

    def test_original_archive_preprocessors(self):
        expected = {
            'paper-checker': ('files.tar.gz', 'my_paper'),
            'reimbursement-form-filler': ('bills/bills.tar.gz', 'bills'),
            'arrange-workspace': ('initial_workspace.tar.gz', None),
            'courses-ta-hws': ('files.tar.gz', None),
            'privacy-desensitization':
            ('files.tar.gz', 'desensitized_documents'),
        }
        for task, (archive, directory) in expected.items():
            with self.subTest(
                    task=task), tempfile.TemporaryDirectory() as temp:
                work = Path(temp)
                shutil.copytree(toolathlon.task_dir(task) /
                                'initial_workspace',
                                work,
                                dirs_exist_ok=True)
                toolathlon.prepare_workspace(task, work)
                self.assertFalse((work / archive).exists())
                self.assertTrue(any(p.is_file() for p in work.rglob('*')))
                if directory:
                    self.assertTrue((work / directory).is_dir())
                self.assertFalse((work / 'initial_workspace_arrange').exists())
                if task == 'reimbursement-form-filler':
                    self.assertTrue(list((work / 'bills').glob('*.pdf')))

    def test_regenerated_homepage_mail(self):
        from server.seed.seed_task import mail_fixture
        data = json.loads(mail_fixture('email-paper-homepage').read_text())
        text = json.dumps(data)
        self.assertIn('COML 2025', text)
        self.assertNotIn('COML 2026', text)
        self.assertEqual(len(data['emails']), data['total_emails'])

    async def test_search_is_routed_through_shared_transport(self):
        from server.seed import research
        toolathlon.root()
        import importlib
        original = importlib.import_module('utils.aux_tools.web_search')
        with patch.dict(os.environ, {'SERPER_API_KEY': 'test-only'}), \
                patch.object(original, 'on_web_search_tool_invoke',
                             AsyncMock(return_value='original search result')
                             ) as search:
            with research.transport('course-schedule') as (url, _):
                with patch.dict(os.environ, {'SEARCH_CLI_URL': url}):
                    result = await research.search_tool(
                        None, '{"query":"fixture"}')
                    self.assertEqual(result, 'original search result')
                    search.assert_awaited_once()
                    # The MCP tool keeps its original schema, but always
                    # invokes this transport, even outside the research set.
                    import arms
                    with patch.object(
                            arms,
                            'needed_local_tools',
                            return_value=['web_search']), patch.object(
                                arms,
                                'airgapped_tool',
                                side_effect=lambda tool: tool), patch.object(
                                    arms,
                                    'truncating_tool',
                                    side_effect=lambda tool: tool):
                        tools = arms.build_local_tools(
                            toolathlon.local('course-schedule'))
                    self.assertIs(tools[0].on_invoke_tool,
                                  research.search_tool)

    def test_course_schedule_shell_reaches_the_search_transport(self):
        # Its prompt names `web-search web_search`, which its workspace once
        # did not have. The yaml's own block is resolved and run, less the
        # task's other CLIs and its Python.
        import workspace as backend

        from server.seed import research
        toolathlon.root()
        import importlib
        original = importlib.import_module('utils.aux_tools.web_search')
        resolve = backend.resolved
        config = backend.config_for(REPO / 'task/toolathlon/course-schedule')
        # The dropped CLIs' addresses are interpolated before they are
        # dropped, so each needs a value; none is ever called.
        env = {
            name: 'http://127.0.0.1:9'
            for name in re.findall(r'\$\{(\w+)\}', config.read_text())
        }
        env['SERPER_API_KEY'] = 'test-only'
        search = AsyncMock(return_value='original search result')
        command = 'web-search web_search \'{"query":"fixture"}\''

        def search_only(path):
            body = resolve(path)
            body['runtimes'] = ['workspace']
            body['clis'] = {'web-search': body['clis']['web-search']}
            return body

        with tempfile.TemporaryDirectory() as work, patch.dict(
                os.environ, env, AGENT_WORKSPACE=work), patch.object(
                    original, 'on_web_search_tool_invoke', search):
            with research.transport('course-schedule') as (url, _):
                with patch.dict(os.environ, SEARCH_CLI_URL=url), patch.object(
                        backend, 'resolved', side_effect=search_only):
                    ws = backend.Workspace.create(config)
                try:
                    self.assertEqual(
                        ws.execute(command).strip(), 'original search result')
                finally:
                    ws.close()

    def test_pdf_tools_keeps_upstreams_network(self):
        # Every pdf-tools tool that takes a PDF takes a URL and downloads it,
        # as upstream's does with its network; pptx has no such tool and
        # stays on the loopback. Both arms ask `prefix` for the network, and
        # what each platform makes of it is `prefix`'s own branch.
        from server import execution
        from server.mcp.mcp_servers import build_mcp_servers
        from server.seed import travel_video

        def prefix(workdir, readable=(), writable=(), *, public_network):
            return ['public' if public_network else 'loopback']

        def client_thread(kind, endpoint, params, log, virtual_root):
            launched[kind] = params['command']
            endpoint.write_text('http://127.0.0.1:9')
            return None, lambda: None

        launched = {}
        with tempfile.TemporaryDirectory() as work, patch.object(
                execution, 'prefix',
                prefix), patch.object(travel_video, 'client_thread',
                                      client_thread):
            servers = {
                server.name: server.params.command
                for server in build_mcp_servers(
                    toolathlon.local('ppt-analysis'), work)
            }
            with travel_video.serve_tools(['pdf-tools', 'pptx'], work):
                pass
        self.assertEqual((servers['pdf-tools'], servers['pptx']),
                         ('public', 'loopback'))
        self.assertEqual(launched, {'pdf-tools': 'public', 'pptx': 'loopback'})

    def test_git_milestone_grader_signs_live_github_as_the_operator(self):
        # Upstream's evaluator refetches api.github.com with the "XX" its
        # token file ships, and falls back to a months-old snapshot on the
        # 401. Its shim signs GitHub calls with the operator's token and
        # leaves every other request as the evaluator built it.
        from task.toolathlon.script.grade_task import redirection
        paths, _, _ = redirection('git-milestone')
        shim = toolathlon.local('git-milestone') / 'toolathlon/eval_shim'
        self.assertIn(str(shim), paths)
        probe = '\n'.join((
            'import requests',
            'from requests.adapters import HTTPAdapter',
            'def send(self, request, **kwargs):',
            '    print(request.url, request.headers["Authorization"])',
            '    response = requests.Response()',
            '    response.status_code = 200',
            '    return response',
            'HTTPAdapter.send = send',
            'for url in ("https://api.github.com/repositories/1",',
            '            "http://127.0.0.1:19801/repos/a/b"):',
            '    requests.get(url, headers={"Authorization": "token XX"})',
        ))
        env = {
            key: value
            for key, value in os.environ.items() if key != 'GITHUB_TOKEN'
        }

        def probed(**token):
            return subprocess.run([sys.executable, '-c', probe],
                                  env={
                                      **env, 'PYTHONPATH': str(shim),
                                      **token
                                  },
                                  capture_output=True,
                                  text=True,
                                  check=True)

        signed = probed(GITHUB_TOKEN='operator-token')
        unsigned = probed()
        self.assertEqual(
            signed.stdout,
            'https://api.github.com/repositories/1 token operator-token\n'
            'http://127.0.0.1:19801/repos/a/b token XX\n')
        self.assertEqual(signed.stderr, '')
        # Without one, the evaluator runs as upstream's does on "XX", and
        # says so where the grade's log will show it.
        self.assertEqual(
            unsigned.stdout, 'https://api.github.com/repositories/1 token XX\n'
            'http://127.0.0.1:19801/repos/a/b token XX\n')
        self.assertIn('GITHUB_TOKEN is unset', unsigned.stderr)

    def test_yahoo_is_live_on_every_task(self):
        # Upstream reads Yahoo live, so no task keeps a copy of it: no
        # manifest seeds market rows, no task holds a capture, and both
        # arms launch the original SDK behind the recording transport.
        from server.mcp.mcp_servers import SERVERS, Launch
        for task_dir in sorted((REPO / 'task/toolathlon').iterdir()):
            if not (task_dir / 'shared/task.md').is_file():
                continue
            if 'yahoo-finance' not in toolathlon.needed_mcp_servers(
                    task_dir.name):
                continue
            with self.subTest(task=task_dir.name):
                manifest = json.loads((task_dir / 'task.json').read_text())
                self.assertNotIn(
                    'market',
                    [fixture['kind'] for fixture in manifest['fixtures']])
                self.assertFalse((task_dir / 'shared/market').exists())
                self.assertFalse((task_dir / 'shared/fixtures/yahoo').exists())
                params = SERVERS['yahoo-finance'](Launch(task_dir, '/tmp'))
                self.assertEqual(params['env']['PYTHONPATH'],
                                 str(REPO / 'redirect/yahoo_capture'))
                # `uv run` builds the vendored lock's environment on a
                # fresh checkout; a bare .venv interpreter has none there.
                self.assertEqual(params['command'], 'uv')
                self.assertEqual(params['args'][:4], [
                    'run', '--locked', '--directory',
                    str(REPO / 'vendor/yahoo-finance-mcp')
                ])

    def test_only_hub_tasks_get_the_hub_redirect(self):
        # `HF_TOKEN` is the task's name, which a task without the Hub would
        # otherwise hand to its model's Python and nothing else.
        import arms
        for name, hub in (('course-schedule', False), ('verl-dataset', True)):
            with self.subTest(task=name), patch.dict(os.environ):
                os.environ.pop('HF_ENDPOINT', None)
                os.environ.pop('HF_TOKEN', None)
                arms.hub_redirect(toolathlon.local(name))
                self.assertEqual(os.environ.get('HF_TOKEN'),
                                 name if hub else None)
                self.assertEqual('HF_ENDPOINT' in os.environ, hub)

    def test_yahoo_receipts_reach_the_run_record(self):
        # The final batch's record carries its recorder's receipts as
        # `public_api_requests`; every other Yahoo task's record does too.
        from contextlib import contextmanager, nullcontext
        receipts = [{'kind': 'yahoo', 'source': 'live'}]

        @contextmanager
        def recorder():
            yield 'http://127.0.0.1:9', receipts

        @contextmanager
        def owned(task, workdir):
            yield None

        with tempfile.TemporaryDirectory() as work, patch(
                'server.seed.public_services.serve',
                recorder), patch.object(toolathlon, '_services', owned), patch(
                    'server.seed.travel_video.serve_tools',
                    lambda *args: nullcontext()):
            with toolathlon.services('stock-build-position', work) as record:
                self.assertIs(record['public_api_requests'], receipts)

    def test_oil_grading_rejects_invalid_prices(self):
        from task.toolathlon.script import grade_task
        rows = [{
            'Date': f'2026-{month:02d}-01',
            'Close': 60.0
        } for month in range(1, 9)]
        grade_task.verify_oil_prices(rows)
        for broken in ([], [*rows, {
                'Date': '2026-09-01',
                'Close': None
        }], [*rows, {
                'Date': '2026-09-01',
                'Close': float('nan')
        }], [*rows, {
                'Date': '2026-09-01'
        }]):
            with self.assertRaisesRegex(RuntimeError, 'invalid prices'):
                grade_task.verify_oil_prices(broken)

    async def test_oil_grading_prices_every_scored_month(self):
        # Upstream's evaluator scores the last twelve complete UTC months and
        # prices a month the series skips by date on its last day; a month
        # it still cannot price drops out of its comparison silently.
        from datetime import datetime, timezone

        from task.toolathlon.script import grade_task
        now = datetime(2026, 9, 25, tzinfo=timezone.utc)
        months = grade_task.oil_months(now)
        self.assertEqual((months[0], months[-1], len(months)),
                         ('2025-09', '2026-08', 12))
        self.assertEqual(
            grade_task.oil_months(datetime(2026, 1, 5, tzinfo=timezone.utc)),
            [f'2025-{month:02d}' for month in range(1, 13)])
        rows = [{
            'Date': f'{month}-01T04:00:00.000Z',
            'Close': 60.0
        } for month in months if month != '2026-02']

        def session(answer):
            calls = []

            async def call_tool(name, arguments):
                calls.append((name, arguments))
                return SimpleNamespace(isError=False,
                                       content=[SimpleNamespace(text=answer)])

            return SimpleNamespace(call_tool=call_tool), calls

        priced, calls = session(json.dumps({'close': 61.5}))
        await grade_task.verify_oil_months(priced, 'CL=F', rows, now)
        self.assertEqual(calls, [('get_stock_price_by_date', {
            'ticker': 'CL=F',
            'date': '2026-02-28'
        })])
        unpriced, _ = session('No trading data found for CL=F')
        with self.assertRaisesRegex(RuntimeError,
                                    'cannot price CL=F for 2026-02'):
            await grade_task.verify_oil_months(unpriced, 'CL=F', rows, now)

    def test_oil_grading_rebuilds_config_and_propagates_failure(self):
        from server.mcp.mcp_servers import upstream_config
        from task.toolathlon.script import grade_task
        original = upstream_config('yahoo-finance')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            configs = root / 'configs/mcp_servers'
            configs.mkdir(parents=True)
            path = configs / 'yahoo-finance.yaml'
            path.write_text('broken: true')
            with patch.object(dataset, 'root', return_value=root), patch(
                    'server.mcp.mcp_servers.upstream_config',
                    return_value=original), patch.object(
                        grade_task, 'verify_oil_transport',
                        AsyncMock(side_effect=RuntimeError('no prices'))):
                with self.assertRaisesRegex(RuntimeError, 'no prices'):
                    grade_task.prepare_evaluator_services('oil-price', root)
            import yaml
            config = yaml.safe_load(path.read_text())
            self.assertIn('yahoo-finance-mcp',
                          ' '.join(config['params']['args']))
            self.assertIn('PYTHONPATH', config['params']['env'])

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS confinement')
    def test_workspace_ancestor_listing_denied(self):
        from server.execution import launch
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            work = parent / 'run'
            work.mkdir()
            (parent / 'sibling-secret').mkdir()
            script = "import os; print(os.listdir('.')); os.listdir('..')"
            params = launch(
                {
                    'command': sys.executable,
                    'args': ['-c', script],
                    'env': os.environ
                },
                work,
                readable=[Path(sys.prefix),
                          Path(sys.base_prefix)])
            result = subprocess.run([params['command'], *params['args']],
                                    cwd=work,
                                    env=params['env'],
                                    capture_output=True,
                                    text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('PermissionError', result.stderr)
            self.assertNotIn('sibling-secret', result.stdout)

    # Upstream gives these to their servers alone, so neither the model's
    # Python nor the terminal server's commands may see them.
    SERVER_ENV = {
        'WOOCOMMERCE_CONSUMER_KEY': 'ck_test',
        'WOOCOMMERCE_CONSUMER_SECRET': 'cs_test',
        'WORDPRESS_SITE_URL': 'http://localhost:10003/store',
        'CANVAS_API_TOKEN': 'canvas',
        'GOOGLE_REFRESH_TOKEN': 'refresh',
        'GWS_URL': 'http://127.0.0.1:19999',
    }

    async def test_python_tool_environment_holds_no_server_credentials(self):
        # The Hub redirect is the one service setting the model's Python is
        # meant to have.
        from server.execution import python_tool
        servers = self.SERVER_ENV
        hub = {'HF_ENDPOINT': 'http://127.0.0.1:5199', 'HF_TOKEN': 'task'}
        code = 'import json, os; print(json.dumps(sorted(os.environ)))'
        with tempfile.TemporaryDirectory() as temp, patch.dict(
                os.environ, {
                    **servers,
                    **hub
                }):
            context = SimpleNamespace(
                context={'_agent_workspace': str(Path(temp).resolve())})
            out = await python_tool(context, json.dumps({'code': code}))
        names = set(json.loads(
            out.split('=== STDOUT ===\n')[1].split('\n')[0]))
        self.assertEqual(names & set(servers), set())
        self.assertLessEqual(set(hub), names)

    async def test_python_tool_runs_the_kubernetes_wrappers(self):
        # A Kubernetes task's PATH puts server/kubectl.sh and server/helm.sh
        # first, and they exec the binaries their settings name. helm also
        # gets an empty Docker config inside its own config home.
        from server.execution import python_tool
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            tools, native, config = (root / name
                                     for name in ('k8s', 'native', 'helm'))
            for folder in (tools, native, config, root / 'work'):
                folder.mkdir()
            echo = '#!/bin/sh\necho "$@" "$HELM_CONFIG_HOME" $DOCKER_CONFIG\n'
            for name in ('kubectl', 'helm'):
                shutil.copyfile(REPO / f'server/{name}.sh', tools / name)
                (native / name).write_text(echo)
                (tools / name).chmod(0o755)
                (native / name).chmod(0o755)
            kubeconfig = root / 'config.yaml'
            kubeconfig.write_text('')
            code = ('import subprocess\n'
                    "for c in (['kubectl', 'get', 'pods'], ['helm', 'repo', "
                    "'add', 'x', 'https://charts.bitnami.com/bitnami']):\n"
                    '    print(subprocess.run(c, capture_output=True, '
                    'text=True).stdout, end="")')
            with patch.dict(
                    os.environ, {
                        'PATH': f'{tools}{os.pathsep}{os.environ["PATH"]}',
                        'KUBECONFIG': str(kubeconfig),
                        'KUBECTL': str(tools / 'kubectl'),
                        'KUBECTL_NATIVE': str(native / 'kubectl'),
                        'K8S_PROCESS_DIR': str(tools),
                        'HELM_NATIVE': str(native / 'helm'),
                        'HELM_FIXTURE_URL': 'http://127.0.0.1:8085',
                        'HELM_CONFIG_HOME': str(config),
                    }):
                context = SimpleNamespace(
                    context={'_agent_workspace': str(root / 'work')})
                out = await python_tool(context, json.dumps({'code': code}))
        self.assertIn(f'--kubeconfig {kubeconfig} get pods {config}\n', out)
        self.assertIn(
            f'repo add x http://127.0.0.1:8085 {config} {config}/docker\n',
            out)

    @unittest.skipUnless(
        sys.platform == 'darwin'
        and (REPO / 'vendor/kubernetes-bin/helm').is_file(),
        'macOS confinement and the pinned helm')
    def test_confined_helm_starts(self):
        # helm reads the user's ~/.docker/config.json when it starts, which
        # the sandbox denies; on a host that has one, helm exits 1 unless the
        # wrapper points it elsewhere.
        from server.execution import launch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            work, config = root / 'work', root / 'helm-config'
            work.mkdir()
            config.mkdir()
            wrapper = root / 'helm'
            shutil.copyfile(REPO / 'server/helm.sh', wrapper)
            wrapper.chmod(0o755)
            params = launch(
                {
                    'command': str(wrapper),
                    'args': ['version', '--short'],
                    'env': {
                        **os.environ,
                        'HELM_NATIVE':
                        str(REPO / 'vendor/kubernetes-bin/helm'),
                        'HELM_CONFIG_HOME':
                        str(config),
                    }
                }, work)
            result = subprocess.run([params['command'], *params['args']],
                                    cwd=work,
                                    env=params['env'],
                                    capture_output=True,
                                    text=True,
                                    timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')

    def test_terminal_environment_holds_no_server_credentials(self):
        from server import shared_workspace
        from server.execution import launch
        from server.mcp import mcp_servers
        with tempfile.TemporaryDirectory() as temp, patch.dict(
                os.environ,
                self.SERVER_ENV), patch.object(shared_workspace, 'CURRENT',
                                               None):
            at = mcp_servers.Launch(toolathlon.local('course-schedule'),
                                    str(Path(temp).resolve()))
            env = launch(mcp_servers.terminal(at), at.workdir)['env']
        self.assertEqual(set(env) & set(self.SERVER_ENV), set())
        self.assertIn('ALLOWED_COMMANDS', env)
        self.assertIn('PATH', env)


class UpstreamImage(unittest.IsolatedAsyncioTestCase):
    """The model's tools in upstream's own task image, as upstream runs
    them."""

    def setUp(self):
        dataset.use('toolathlon')

    async def test_python_tool_runs_in_the_upstream_image(self):
        # Upstream's interpreter and libraries, its GNU tools and network,
        # and no boundary short of the container: the parent directory, the
        # process table and git are all there, as they are upstream.
        from server.execution import python_tool, upstream_container
        code = ('import os, subprocess, sys, pandas\n'
                'print(sys.executable, sys.version.split()[0], '
                'pandas.__version__)\n'
                'print(os.listdir(".."))\n'
                "print(subprocess.run(['find', '.', '-maxdepth', '0', "
                "'-printf', '%p'], capture_output=True, text=True).stdout)\n"
                "print(subprocess.run(['ps', '-o', 'comm=', '-p', '1'], "
                'capture_output=True, text=True).stdout.strip())\n'
                "open('made.txt', 'w').write('x')\n")
        servers = {'WOOCOMMERCE_CONSUMER_KEY': 'ck_test'}
        with tempfile.TemporaryDirectory() as temp, patch.dict(
                os.environ, servers):
            work = Path(temp).resolve() / 'workspace'
            work.mkdir()
            with upstream_container(work):
                context = SimpleNamespace(
                    context={'_agent_workspace': str(work)})
                out = await python_tool(context, json.dumps({'code': code}))
                env = await python_tool(
                    context,
                    json.dumps(
                        {'code': 'import os; print(sorted(os.environ))'}))
            self.assertEqual((work / 'made.txt').read_text(), 'x')
        self.assertIn('/workspace/.venv/bin/python3 3.12.11 2.2.3\n', out)
        self.assertIn("['workspace']\n.\ndocker-init\n", out)
        self.assertNotIn('WOOCOMMERCE_CONSUMER_KEY', env)

    async def test_a_cancelled_call_leaves_nothing_running(self):
        # Stopping the docker client stops nothing in the container, so a
        # call the run's wall clock cancels takes its process group with it.
        import asyncio

        from server.execution import python_tool, upstream_container
        code = "open('started', 'w').close()\nimport time\ntime.sleep(60)\n"
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp).resolve() / 'workspace'
            work.mkdir()
            with upstream_container(work) as box:
                context = SimpleNamespace(
                    context={'_agent_workspace': str(work)})
                call = asyncio.create_task(
                    python_tool(context, json.dumps({'code': code})))
                for _ in range(120):
                    if (work / 'started').exists():
                        break
                    await asyncio.sleep(0.5)
                call.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await call
                left = subprocess.run(
                    ['docker', 'exec', box['id'], 'ps', '-eo', 'comm='],
                    capture_output=True,
                    text=True).stdout.split()
        self.assertEqual(sorted(left), ['docker-init', 'ps', 'sleep'])

    def test_terminal_and_filesystem_launch_in_the_container(self):
        # Upstream's own terminal line, and the filesystem server npx
        # resolves from upstream's npm tree, both run from the workspace.
        import yaml

        from server import execution, shared_workspace
        from server.mcp import mcp_servers
        workdir = '/tmp/work'
        box = {'id': 'box', 'workdir': workdir, 'env': {}}
        with patch.object(execution, 'CONTAINER',
                          box), patch.object(shared_workspace, 'CURRENT',
                                             None):
            at = mcp_servers.Launch(toolathlon.local('course-schedule'),
                                    workdir)
            terminal = mcp_servers.terminal(at)
            files = mcp_servers.filesystem(at)
        config = yaml.safe_load(
            mcp_servers.upstream_config('terminal'))['params']
        self.assertEqual(terminal['command'], 'docker')
        self.assertEqual(terminal['args'][-len(config['args']) - 2:],
                         ['box', config['command'], *config['args']])
        self.assertIn(f'ALLOWED_DIR={workdir}', terminal['args'])
        self.assertEqual(files['args'][:4],
                         ['exec', '--interactive', '--workdir', workdir])
        self.assertEqual(files['args'][-3:], [
            'node', '/workspace/node_modules/@modelcontextprotocol/'
            'server-filesystem/dist/index.js', workdir
        ])


if __name__ == '__main__':
    unittest.main()
