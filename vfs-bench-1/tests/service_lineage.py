"""Original task bytes, complete MCP locks and immutable service artifacts."""
import fcntl
import gzip
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server.execution import prefix  # noqa: E402
from server.fakes import stack as fixture_stack  # noqa: E402
from server.mcp.npm_lock import derive  # noqa: E402
from server.mcp.setup_helm import prepare_repository  # noqa: E402
from server.sandbox import Tunnel  # noqa: E402
from server.seed import business_mail  # noqa: E402
from server.seed.business import setup_args, tokens  # noqa: E402
from server.seed.kubernetes import original  # noqa: E402
from server.seed.seed_mail import connect as mail_connect  # noqa: E402

sys.path.insert(0, str(REPO / 'task/toolathlon/script'))
import capture_redis_charts as redis_charts  # noqa: E402
import dataset  # noqa: E402
import services  # noqa: E402

TASKS = ('k8s-safety-audit', 'k8s-redis-helm-upgrade', 'k8s-mysql',
         'inventory-sync', 'canvas-art-quiz')


@contextmanager
def private_locks():
    """Point the host locks at a scratch directory, away from real runs."""
    with tempfile.TemporaryDirectory() as tmp, patch.object(
            services, 'LOCKS',
            Path(tmp) / 'locks'), patch.object(
                services, 'LEGACY_LOCK',
                Path(tmp) / 'legacy.lock'), redirect_stdout(StringIO()):
        yield Path(tmp)


def entered_within(target, seconds=0.3):
    """Start `target` on a thread and say whether it finished in time."""
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    return thread, not thread.is_alive()


class ServiceLineage(unittest.TestCase):

    def test_startup_reconciles_only_the_draws_services_once(self):
        """Another checkout's draw may be using any other container."""
        spec = yaml.safe_load((REPO / 'docker/compose.yml').read_text())
        always_on = {
            name
            for name, service in spec['services'].items()
            if 'profiles' not in service
        }
        self.assertEqual(set(fixture_stack.CONTAINERS),
                         set(fixture_stack.SERVICE_PORTS))
        self.assertEqual(
            {
                name
                for names in fixture_stack.CONTAINERS.values()
                for name in names
            }, always_on, 'a container no draw starts, or one that is gone')
        with private_locks(), patch.object(
                fixture_stack, 'assemble_fixtures') as assembled, patch.object(
                    fixture_stack, 'pending',
                    return_value=0) as pending, patch.object(
                        fixture_stack, 'compose') as compose, patch.object(
                            fixture_stack, '_image_ready',
                            False), patch.object(fixture_stack, '_started',
                                                 set()):
            fixture_stack.up([])
            fixture_stack.up(['gws'])
            fixture_stack.up(['gws'])
            fixture_stack.up(['hf', 'gws', 'gcp'])
        self.assertEqual(compose.call_args_list, [
            call('build', 'api', check=True),
            call('up', '-d', '--no-deps', 'gws', check=True),
            call('up', '-d', '--no-deps', 'hfhub', 'api', check=True),
        ])
        self.assertEqual(
            assembled.call_args_list,
            [call(['gws']),
             call(['gws']),
             call(['hf', 'gws', 'gcp'])])
        self.assertEqual(pending.call_args_list[-1],
                         call(['hfhub', 'gws', 'api']))

    def test_startup_syncs_only_the_draws_fixture_trees(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,
                                                              STACK_DIR=tmp):
            root = fixture_stack.assemble_fixtures(['gws'])
            self.assertEqual([path.name for path in root.iterdir()], ['gws'])
            # Another draw's tree, synced there from another checkout.
            theirs = root / 'hf-hub' / 'theirs.json'
            theirs.parent.mkdir()
            theirs.write_text('seeded')
            (root / 'hf-hub' / '.assembled').write_text('["theirs.json"]')
            fixture_stack.assemble_fixtures(['gws', 'notion'])
            self.assertEqual(theirs.read_text(), 'seeded')
            self.assertTrue((root / 'notion' / 'empty.json').is_file())
            self.assertTrue((root / 'gws' / '.assembled').is_file())

    def test_draws_wait_only_for_what_they_share(self):
        with private_locks():
            held, release = threading.Event(), threading.Event()

            def owner():
                with services.holding(['stack-mail-1143', 'task-a']):
                    held.set()
                    release.wait(10)

            threading.Thread(target=owner, daemon=True).start()
            self.assertTrue(held.wait(10))
            _, apart = entered_within(
                lambda: services.holding(['task-b']).__enter__())
            waiting, shared = entered_within(
                lambda: services.holding(['stack-mail-1143']).__enter__())
            self.assertTrue(apart, 'a draw sharing nothing waited')
            self.assertFalse(shared, 'a draw sharing mail did not wait')
            release.set()
            waiting.join(10)
            self.assertFalse(waiting.is_alive())

    def test_a_runner_on_older_code_excludes_draws(self):
        with private_locks() as tmp:
            with (tmp / 'legacy.lock').open('a+') as older:
                fcntl.flock(older.fileno(), fcntl.LOCK_EX)
                waiting, entered = entered_within(
                    lambda: services.holding(['task-a']).__enter__())
                self.assertFalse(entered, 'a draw overlapped older code')
                fcntl.flock(older.fileno(), fcntl.LOCK_UN)
                waiting.join(10)
                self.assertFalse(waiting.is_alive())
            with services.holding(['task-b']):
                _, beside = entered_within(
                    lambda: services.holding(['task-c']).__enter__())
            self.assertTrue(beside, 'two draws on this code did not overlap')

    def test_a_draw_holds_only_the_stack_services_its_task_reaches(self):
        import run_agent
        dataset.use('toolathlon')
        ports = ('GWS_PORT', 'GITHUB_PORT', 'NOTION_PORT', 'HF_HUB_PORT',
                 'PG_PORT', 'BQ_PORT')
        with patch.dict(os.environ, {name: ''
                                     for name in ports}), private_locks():
            for name in ports:
                del os.environ[name]
            for task in dataset.tasks():
                self.assertLessEqual(set(fixture_stack.used(task)),
                                     set(fixture_stack.SERVICE_PORTS), task)
            self.assertEqual(fixture_stack.used('arrange-workspace'), [])
            self.assertEqual(
                run_agent.draw_locks(REPO /
                                     'task/toolathlon/arrange-workspace'),
                ['task-toolathlon-arrange-workspace'])
            self.assertEqual(
                run_agent.draw_locks(REPO / 'task/toolathlon/set-conf-cr-ddl'),
                [
                    'task-toolathlon-set-conf-cr-ddl', 'stack-gws-19999',
                    'stack-mail-1143', 'conflict-set-conf-cr-ddl'
                ])
            self.assertEqual(
                run_agent.draw_locks(REPO / 'task/toolathlon/canvas-do-quiz'),
                [
                    'task-toolathlon-canvas-do-quiz',
                    'conflict-canvas-do-quiz', 'port-10001'
                ])

    def test_a_draw_takes_its_locks_without_the_root_on_the_path(self):
        # `run_agent.py` runs as a script, so only its own imports put the
        # root on `sys.path`. Take the root and `server` away, as a draw
        # starts, and load `stack` the way run_agent's path reaches it.
        dataset.use('toolathlon')
        path = list(sys.path)
        modules = {
            name: module
            for name, module in sys.modules.items()
            if name in ('server', 'stack') or name.startswith('server.')
        }
        try:
            sys.path[:] = [
                str(REPO / 'server/fakes'),
                *(p for p in path if Path(p or '.').resolve() != REPO)
            ]
            for name in modules:
                del sys.modules[name]
            import stack
            self.assertEqual(stack.used('arrange-workspace'), [])
        finally:
            sys.path[:] = path
            for name in [
                    name for name in sys.modules
                    if name in ('server',
                                'stack') or name.startswith('server.')
            ]:
                del sys.modules[name]
            sys.modules.update(modules)

    def test_a_seed_empties_only_the_services_its_task_uses(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
                os.environ, STACK_DIR=tmp), patch.object(
                    fixture_stack,
                    'post') as post, redirect_stdout(StringIO()):
            for name in ('GWS_PORT', 'GITHUB_PORT', 'MAIL_API_PORT'):
                os.environ.pop(name, None)
            logs = Path(tmp) / 'cloud_logging'
            for task in ('mine', 'theirs'):
                (logs / task).mkdir(parents=True)
            fixture_stack.reset('arrange-workspace', [])
            post.assert_not_called()
            fixture_stack.reset('set-conf-cr-ddl', ['gws', 'mail'])
            self.assertEqual(post.call_args_list, [
                call('http://127.0.0.1:19999/reset', {}),
                call('http://127.0.0.1:8081/api/service/reset', None),
            ])
            post.reset_mock()
            fixture_stack.reset('git-repo', ['github'])
            post.assert_called_once_with('http://127.0.0.1:19801/reset',
                                         {'fixture': 'empty'})
            fixture_stack.reset('mine', ['gcp'])
            self.assertEqual(sorted(p.name for p in logs.iterdir()),
                             ['theirs'])

    def test_fixture_sync_never_leaves_a_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            into = Path(tmp) / 'integ'

            def staged(text, *extra):
                source = Path(tempfile.mkdtemp(dir=tmp))
                (source / 'notion').mkdir()
                for name in ('task.json', *extra):
                    (source / 'notion' / name).write_text(text)
                return source

            fixture_stack.sync(staged('0', 'dropped.json'), into)
            # What a GitHub or Hub seed stages mid-draw, which no sync wrote.
            (into / 'github').mkdir()
            (into / 'github' / 'seeded.json').write_text('a task')
            missing, done = [], threading.Event()

            def read():
                while not done.is_set():
                    try:
                        (into / 'notion' / 'task.json').read_text()
                    except FileNotFoundError:
                        missing.append(True)

            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            for number in range(1, 200):
                fixture_stack.sync(staged(str(number)), into)
            done.set()
            reader.join(10)
            self.assertEqual(missing, [], 'a reader found the file gone')
            self.assertFalse((into / 'notion' / 'dropped.json').exists())
            self.assertTrue((into / 'github' / 'seeded.json').exists(),
                            "a sync removed a seeder's fixture")
            before = (into / 'notion' / 'task.json').stat().st_ino
            fixture_stack.sync(staged('199'), into)
            self.assertEqual((into / 'notion' / 'task.json').stat().st_ino,
                             before, 'an unchanged file was rewritten')

    def test_mail_connections_are_finite_and_validation_retries(self):
        account = {
            'imap_server': 'localhost',
            'imap_port': 1143,
            'email': 'person@example.com',
            'password': 'secret'
        }
        client = MagicMock()
        with patch('server.seed.seed_mail.imaplib.IMAP4',
                   return_value=client) as constructor:
            self.assertIs(mail_connect(account), client)
        constructor.assert_called_once_with('localhost', 1143, timeout=10)

        failed = MagicMock()
        failed.select.side_effect = TimeoutError
        healthy = MagicMock()
        healthy.select.return_value = ('OK', [b'0'])
        with tempfile.NamedTemporaryFile(mode='w') as config:
            json.dump(account, config)
            config.flush()
            with patch.dict('os.environ',
                            {'BUSINESS_EMAIL_CONFIG': config.name}), patch(
                                'server.seed.business_mail.connect',
                                side_effect=[failed, healthy]) as reconnect:
                business_mail.assert_empty('woocommerce-new-product')
        self.assertEqual(reconnect.call_count, 2)
        self.assertEqual(healthy.select.call_args_list, [
            call(folder, readonly=True)
            for folder in ('INBOX', 'Sent', 'Drafts', 'Trash', 'Junk')
        ])

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS only')
    def test_confinement_hides_ungranted_file_metadata(self):
        with tempfile.TemporaryDirectory(dir=REPO) as workspace, \
                tempfile.TemporaryDirectory(dir=REPO) as home:
            private = Path(home) / '.netrc'
            private.write_text('secret')
            code = ('import json,os;'
                    f'p={str(private)!r};'
                    'result=[os.path.exists(p)];'
                    '\ntry:\n open(p).read()\n'
                    'except OSError as e:\n result.append(e.errno)\n'
                    'print(json.dumps(result))')
            with patch('server.execution.Path.home', return_value=Path(home)):
                command = prefix(workspace,
                                 readable=[
                                     Path(sys.executable),
                                     Path(sys.prefix),
                                     Path(sys.base_prefix)
                                 ])
            result = subprocess.run([*command, sys.executable, '-c', code],
                                    cwd=workspace,
                                    text=True,
                                    capture_output=True,
                                    check=True)
            self.assertEqual(json.loads(result.stdout), [False, 1])

    def test_e2b_tunnel_does_not_inherit_agent_proxy(self):
        called = threading.Event()
        kwargs = {}

        class Socket:

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def __iter__(self):
                return iter(())

            def close(self):
                pass

        def open_socket(_url, **options):
            kwargs.update(options)
            called.set()
            return Socket()

        with patch('server.sandbox.connect', open_socket):
            tunnel = Tunnel('wss://sandbox.invalid')
            try:
                with socket.create_connection(('127.0.0.1', tunnel.port)):
                    self.assertTrue(called.wait(1))
            finally:
                tunnel.close()
        self.assertIsNone(kwargs['proxy'])

    def test_prompts_are_original(self):
        for task in TASKS:
            self.assertEqual(
                original(f'tasks/finalpool/{task}/docs/task.md'),
                (REPO / f'task/toolathlon/{task}/shared/task.md').read_bytes())

    def test_complete_mcp_dependencies(self):
        from server.mcp.setup_commerce_canvas import verify
        for service, package in [('canvas', 'canvas-mcp-server'),
                                 ('woocommerce', '@lockon0927/woocommerce-mcp')
                                 ]:
            verify(service)
            with tempfile.TemporaryDirectory() as folder:
                derive(package, Path(folder), f'vfs-bench-{service}-mcp')
                for name in ('package.json', 'package-lock.json'):
                    self.assertEqual(
                        (Path(folder) / name).read_bytes(),
                        (REPO / f'vendor/{service}-mcp' / name).read_bytes())

    def test_sheets_resolution_is_fully_locked(self):
        vendor = REPO / 'vendor/google-sheets-mcp'
        record = json.loads((vendor / 'source.json').read_text())
        self.assertEqual(
            hashlib.sha256(original(record['upstream_config'])).hexdigest(),
            record['upstream_config_sha256'])
        project = tomllib.loads((vendor / 'pyproject.toml').read_text())
        self.assertEqual(set(project['project']['dependencies']), {
            f'{name}=={version}'
            for name, version in record['packages'].items()
        })
        lock = tomllib.loads((vendor / 'uv.lock').read_text())

        def normalize(name):
            return name.lower().replace('_', '-')

        pinned = {normalize(p['name']): p for p in lock['package']}
        for name, version in record['packages'].items():
            package = pinned[normalize(name)]
            self.assertEqual(package['version'], version)
            self.assertTrue(package.get('wheels') or package.get('sdist'))

    def test_service_image_and_script_sources(self):
        records = json.loads(
            (REPO / 'server/business-sources.json').read_text())
        for service, digest in records['setup_sha256'].items():
            source = original(f'deployment/{service}/scripts/setup.sh')
            self.assertEqual(hashlib.sha256(source).hexdigest(), digest)
            for image in records['images'][service]:
                self.assertIn(image['source'].encode(), source)
                self.assertRegex(image['pinned'], r'@sha256:[0-9a-f]{64}$')
        self.assertIn(records['wp_cli']['source'].encode(), source)
        self.assertIn(('plugin install woocommerce --version=' +
                       records['woocommerce_version']).encode(), source)

    def test_captured_sheet(self):
        base = REPO / 'task/toolathlon/k8s-safety-audit/shared/fixtures'
        record = json.loads((base / 'source.json').read_text())
        self.assertEqual(
            hashlib.sha256((base / 'audit.xlsx').read_bytes()).hexdigest(),
            record['sha256'])
        self.assertEqual(
            hashlib.sha256(original(record['preprocess_path'])).hexdigest(),
            record['preprocess_sha256'])

    def test_helm_index_defaults_and_chart_bytes(self):
        base = (REPO / 'task/toolathlon/k8s-redis-helm-upgrade' /
                'shared/fixtures/charts')
        before = yaml.load(gzip.decompress(
            (base / 'index.yaml.gz').read_bytes()),
                           Loader=yaml.CSafeLoader)
        with tempfile.TemporaryDirectory() as folder:
            prepare_repository(Path(folder) / 'charts')
            after = yaml.load((Path(folder) / 'charts/index.yaml').read_text(),
                              Loader=yaml.CSafeLoader)
            # Every Redis version the original index advertises is served
            # out of the capture, and each archive is the bytes the index
            # names: no entry reaches for Bitnami, and none is hidden to
            # make the catalog match a smaller capture.
            for entry in after['entries']['redis']:
                (url, ) = entry['urls']
                self.assertNotIn('://', url)
                self.assertEqual(
                    hashlib.sha256((Path(folder) / 'charts' /
                                    url).read_bytes()).hexdigest(),
                    entry['digest'].removeprefix('sha256:'))
        # Transport URLs alone change. In particular, don't make 22.0.0 the
        # default by publishing an index containing only the target version.
        for entry in after['entries']['redis']:
            original_entry = next(e for e in before['entries']['redis']
                                  if e['version'] == entry['version'])
            entry['urls'] = original_entry['urls']
        self.assertEqual(before, after)
        # An OCI chart's manifest is captured beside it, names the same
        # bytes, and the receipt hashes both.
        records = {
            record['path']: record
            for record in json.loads((base /
                                      'source.json').read_text())['files']
        }
        for entry in before['entries']['redis']:
            if not entry['urls'][0].startswith(redis_charts.OCI):
                continue
            name = f"redis-{entry['version']}"
            manifest = (base / f'{name}.manifest.json').read_bytes()
            self.assertEqual(redis_charts.layer_digest(manifest),
                             redis_charts.digest(entry))
            self.assertEqual(records[f'{name}.tgz']['manifest_sha256'],
                             hashlib.sha256(manifest).hexdigest())

    def test_woocommerce_setup_selects_the_original_task_account(self):
        args = setup_args('woocommerce', 'inventory-sync').split()
        self.assertEqual(args[0], 'start')
        users = json.loads(original('configs/users_data.json'))['users']
        selected = users[int(args[1]) - 1:int(args[1]) - 1 + int(args[2])]
        self.assertEqual(len(selected), 1)
        identity = tokens('inventory-sync')
        self.assertEqual(selected[0]['woocommerce_consumer_key'],
                         identity.woocommerce_api_key)
        self.assertTrue(
            identity.woocommerce_site_url.endswith('/store' +
                                                   str(selected[0]['id'])))

    def test_art_quiz_identity_matches_original_grader(self):
        config = original('tasks/finalpool/canvas-art-quiz/evaluation/main.py')
        self.assertIn(b'from other_key import all_token_key_session', config)
        self.assertTrue(tokens('canvas-art-quiz').canvas_api_token)


if __name__ == '__main__':
    unittest.main()
