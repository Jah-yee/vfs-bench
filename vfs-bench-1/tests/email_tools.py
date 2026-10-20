"""Exact email CLI lineage plus an owned GreenMail integration."""
import email
import email.utils
import imaplib
import json
import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests
import yaml

REPO = Path(__file__).resolve().parents[1]
for directory in ('', 'agent', 'task'):
    sys.path.insert(0, str(REPO / directory))

import toolathlon  # noqa: E402
import workspace as workspace_backend  # noqa: E402
from workspace import Workspace  # noqa: E402

from server.clients.original_tools import (  # noqa: E402
    email_workspace_request, email_workspace_response)
from server.mcp.setup_email import verify  # noqa: E402
from server.seed.business_mail import run_args  # noqa: E402
from server.seed.seed_mail import fill, reset  # noqa: E402
from server.seed.travel_video import serve_tools  # noqa: E402

TOOLS = {
    'get_emails', 'read_email', 'search_emails', 'send_email', 'reply_email',
    'forward_email', 'delete_email', 'move_email', 'mark_emails',
    'move_emails', 'delete_emails', 'get_folders', 'create_folder',
    'delete_folder', 'get_mailbox_stats', 'get_unread_count',
    'check_connection', 'get_email_headers', 'save_draft', 'get_drafts',
    'update_draft', 'delete_draft', 'export_emails', 'import_emails',
    'download_attachment'
}


def available(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.2):
            return True
    except OSError:
        return False


@contextmanager
def greenmail():
    """Start the pinned mail fixture on private, Docker-assigned ports."""
    source = json.loads((REPO / 'server/mail-sources.json').read_text())
    args = [
        'docker', 'run', '--detach', '--rm', '--publish', '127.0.0.1::3025',
        '--publish', '127.0.0.1::3143', '--publish', '127.0.0.1::8080'
    ]
    args += run_args(source['service'], source['pinned'])
    container = subprocess.check_output(args, text=True).strip()
    try:

        def port(number):
            output = subprocess.check_output(
                ['docker', 'port', container, f'{number}/tcp'], text=True)
            return int(output.strip().splitlines()[0].rsplit(':', 1)[1])

        ports = {
            'smtp': port(3025),
            'imap': port(3143),
            'api_port': port(8080)
        }
        ports['api'] = f"http://127.0.0.1:{ports['api_port']}"
        for _ in range(200):
            try:
                ready = requests.get(ports['api'] + '/api/service/readiness',
                                     timeout=.2)
                if (available(ports['imap']) and available(ports['smtp'])
                        and ready.status_code == 200):
                    break
            except requests.RequestException:
                pass
            time.sleep(.1)
        else:
            raise RuntimeError('owned GreenMail fixture did not start')
        yield ports
    finally:
        subprocess.run(['docker', 'rm', '-f', container],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       check=False)


@contextmanager
def mirage_daemon():
    """Start an isolated TypeScript daemon owned by this test process."""
    state = REPO / 'state'
    state.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='email-mirage-',
                                     dir=state) as directory:
        root = Path(directory)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        token = 'email-test-' + secrets.token_hex(16)
        running = workspace_backend.Daemon(f'http://127.0.0.1:{port}', token,
                                           workspace_backend.code_sha())
        saved_running = workspace_backend._RUNNING
        saved_env = {
            key: os.environ.get(key)
            for key in ('STACK_DIR', 'MIRAGE_DAEMON_PORT', 'MIRAGE_AUTH_TOKEN')
        }
        os.environ.update(STACK_DIR=str(root / 'stack'),
                          MIRAGE_DAEMON_PORT=str(port),
                          MIRAGE_AUTH_TOKEN=token)
        log = (root / 'daemon.log').open('wb')
        process = subprocess.Popen(
            ['node', str(workspace_backend.DAEMON)],
            env={
                **os.environ,
                'MIRAGE_HOME': str(root / 'home'),
                'MIRAGE_AUTH_MODE': 'token',
                'SHIM_PYTHON': sys.executable,
            },
            stdout=log,
            stderr=subprocess.STDOUT)
        try:
            for _ in range(300):
                if workspace_backend._alive(running):
                    break
                return_code = process.poll()
                if return_code is not None:
                    log.flush()
                    detail = (root / 'daemon.log').read_text(errors='replace')
                    raise RuntimeError(
                        f'owned Mirage daemon exited {return_code}: {detail}')
                time.sleep(.1)
            else:
                raise RuntimeError('owned Mirage daemon did not start')
            workspace_backend._RUNNING = running
            yield running
        finally:
            workspace_backend._RUNNING = saved_running
            from server.seed.papers import close
            close(process)
            log.close()
            for key, value in saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


class EmailLineage(unittest.TestCase):

    def test_capture_and_task_registrations_match_upstream(self):
        from server.mcp.mcp_servers import upstream_config

        verify()
        captured = json.loads(
            (REPO / 'vendor/emails-mcp/tools.json').read_text())['tools']
        self.assertEqual({tool['name'] for tool in captured}, TOOLS)
        self.assertEqual(len(captured), len(TOOLS))

        local = REPO / 'task/toolathlon'
        tasks = [
            path.name for path in local.iterdir()
            if (path / 'vfs/workspace.yaml').is_file()
        ]
        expected = {
            task
            for task in tasks
            if 'emails' in toolathlon.needed_mcp_servers(task)
        }
        upstream_timeout = yaml.safe_load(
            upstream_config('emails'))['client_session_timeout_seconds'] * 1000
        self.assertEqual(upstream_timeout, 120000)
        lineage = (REPO / 'dvc.yaml').read_text()
        registered = set()
        for task in tasks:
            root = local / task / 'vfs'
            workspace = yaml.safe_load((root / 'workspace.yaml').read_text())
            clis = workspace.get('clis', {})
            if 'emails' not in clis:
                continue
            registered.add(task)
            self.assertEqual(
                clis['emails'], {
                    'cli': '../../../../cli/toolathlon/emails.mjs:EMAILS',
                    'config': {
                        'apiBase': '${EMAILS_CLI_URL}',
                        'timeoutMs': upstream_timeout
                    }
                })
            self.assertNotIn('himalaya', clis)
            self.assertEqual(workspace['mounts']['/mail']['vfs'], 'email')
            for name in ('SKILL.md', 'VFS.md'):
                text = (root / name).read_text()
                self.assertNotIn('himalaya', text.lower())
            skills = (root / 'SKILL.md').read_text()
            self.assertIn("emails <command> '<JSON arguments>'", skills)
            for name in ('move-email', 'delete-email', 'move-emails',
                         'delete-emails'):
                self.assertIn(f'| `emails {name}` |', skills)
            upstream_task = ('submodule/Toolathlon/tasks/finalpool/' + task +
                             '/task_config.json')
            self.assertIn(upstream_task, lineage)
            if task in ('set-conf-cr-ddl', 'student-interview'):
                self.assertEqual(workspace['mounts']['/workspace'], {
                    'vfs': 'disk',
                    'config': {
                        'root': '${AGENT_WORKSPACE}'
                    }
                })
        self.assertEqual(registered, expected)

        for task in expected:
            path = local / task / 'tests/parity.json'
            if not path.is_file():
                continue
            for case in json.loads(path.read_text()).get('cases', []):
                command = case.get('mirage', {}).get('command', '')
                self.assertNotIn('himalaya', command,
                                 f'{task}: stale parity command')

    def test_virtual_workspace_paths_are_transport_only(self):
        for virtual_root in ('/work', '/workspace'):
            with self.subTest(virtual_root=virtual_root):
                self.check_virtual_workspace_paths(virtual_root)

    def check_virtual_workspace_paths(self, virtual_root):

        def map_request(body):
            return email_workspace_request(body, virtual_root)

        def map_response(operation, result):
            return email_workspace_response(operation, result, virtual_root)

        before = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                workspace = Path.cwd()
                request = map_request({
                    'name': 'send_email',
                    'arguments': {
                        'attachments':
                        [virtual_root + '/report.pdf', 'relative.txt']
                    }
                })
                self.assertEqual(request['arguments']['attachments'], [
                    str(workspace / 'report.pdf'),
                    str(workspace / 'relative.txt')
                ])
                invalid = map_request({
                    'name': 'send_email',
                    'arguments': {
                        'attachments': virtual_root + '/report.pdf'
                    }
                })
                self.assertEqual(invalid['arguments']['attachments'],
                                 virtual_root + '/report.pdf')
                invalid_member = map_request({
                    'name': 'send_email',
                    'arguments': {
                        'attachments': [7]
                    }
                })
                self.assertEqual(invalid_member['arguments']['attachments'],
                                 [7])
                for arguments in ([], [['folder', 'INBOX']]):
                    with self.subTest(arguments=arguments):
                        invalid_arguments = {
                            'name': 'get_emails',
                            'arguments': arguments,
                        }
                        self.assertIs(map_request(invalid_arguments),
                                      invalid_arguments)
                imported = map_request({
                    'name': 'import_emails',
                    'arguments': {
                        'import_path': virtual_root + '/export.json'
                    }
                })
                self.assertEqual(imported['arguments']['import_path'],
                                 str(workspace / 'export.json'))
                invalid_import = map_request({
                    'name': 'import_emails',
                    'arguments': {
                        'import_path': 7
                    }
                })
                self.assertEqual(invalid_import['arguments']['import_path'], 7)
                (workspace / 'escape').symlink_to(workspace.parent,
                                                  target_is_directory=True)
                for path in (virtual_root + '//outside', virtual_root +
                             '/../outside', virtual_root + '/a/../../outside',
                             virtual_root + '/./outside',
                             virtual_root + '/escape/outside', '/etc/passwd',
                             str(workspace.parent / 'outside'), '../outside',
                             'a/../../outside'):
                    with self.subTest(
                            path=path), self.assertRaises(ValueError):
                        map_request({
                            'name': 'import_emails',
                            'arguments': {
                                'import_path': path
                            }
                        })
                ordinary = [
                    ('read_email', 'Text Content:\nKeep ' + str(workspace)),
                    ('search_emails', 'Search query: ' + str(workspace)),
                    ('get_emails', 'Subject: saved under ' + str(workspace)),
                ]
                for operation, output in ordinary:
                    with self.subTest(operation=operation):
                        response = map_response(
                            operation, {
                                'content': [{
                                    'type': 'text',
                                    'text': output
                                }],
                                'structuredContent': {
                                    'result': output
                                }
                            })
                        self.assertEqual(response['content'][0]['text'],
                                         output)
                        self.assertEqual(
                            response['structuredContent']['result'], output)

                path_outputs = {
                    'download_attachment':
                    "Attachment 'a.pdf' saved to: " +
                    str(workspace / 'emails_download/a.pdf'),
                    'export_emails':
                    'Successfully exported 2 emails to ' +
                    str(workspace / 'email_exports/INBOX_export.json'),
                    'import_emails':
                    'Error importing emails: Invalid import path: File does '
                    'not exist: ' + str(workspace / 'missing.json'),
                    'send_email':
                    'Error sending email: Failed to send email: Attachment '
                    'error: File does not exist: ' +
                    str(workspace / 'missing.txt'),
                }
                for operation, output in path_outputs.items():
                    with self.subTest(operation=operation):
                        response = map_response(
                            operation, {
                                'content': [{
                                    'type': 'text',
                                    'text': output
                                }],
                                'structuredContent': {
                                    'result': output
                                }
                            })
                        expected = output.replace(str(workspace), virtual_root)
                        self.assertEqual(response['content'][0]['text'],
                                         expected)
                        self.assertEqual(
                            response['structuredContent']['result'], expected)
            finally:
                os.chdir(before)

    def test_business_lifecycle_routes_email_cli_to_remote_config(self):
        """The owned task identity exists before its email CLI is entered."""
        from server.seed import business, travel_video

        task = 'filter-low-selling-products'
        box = SimpleNamespace(sandbox_id='email-lifecycle-test')
        result = SimpleNamespace(stdout='', stderr='', exit_code=0)
        evidence = REPO / 'state/business'
        artifacts = [
            evidence / f'{box.sandbox_id}{suffix}'
            for suffix in ('-setup.log', '-seed.log', '.json')
        ]

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / 'work'
            work.mkdir()
            stale = Path(directory) / 'stale.json'
            remote = Path(directory) / 'remote.json'
            stale.write_text('{}')
            remote.write_text('{}')
            observed = {}

            @contextmanager
            def fake_sandbox(*_args, **_kwargs):
                yield box

            def start_mail(*_args, **_kwargs):
                os.environ.update(BUSINESS_EMAIL_CONFIG=str(remote),
                                  BUSINESS_IMAP_PORT='31001',
                                  BUSINESS_SMTP_PORT='31002')
                return {'fixture': 'remote'}

            @contextmanager
            def original_tools(name, root):
                parameters = travel_video.parameters('emails', root, name)
                index = parameters['args'].index('--config_file') + 1
                observed['task'] = os.environ.get('BUSINESS_TASK')
                observed['config'] = parameters['args'][index]
                yield {}

            def run(_box, command, **_kwargs):
                if 'docker image inspect' in command:
                    return SimpleNamespace(stdout='[]', stderr='', exit_code=0)
                return result

            try:
                with ExitStack() as stack:
                    stack.enter_context(
                        patch.dict(
                            os.environ, {
                                'BUSINESS_TASK': 'previous-task',
                                'BUSINESS_EMAIL_CONFIG': str(stale)
                            }))
                    stack.enter_context(
                        patch.object(business,
                                     'receipt',
                                     return_value={'template_id': 'fixture'}))
                    stack.enter_context(
                        patch.object(business, 'sandbox', fake_sandbox))
                    stack.enter_context(
                        patch.object(business,
                                     'bootstrap',
                                     return_value=({}, result)))
                    for name in ('transfer_in', 'transfer_out'):
                        stack.enter_context(patch.object(business, name))
                    stack.enter_context(
                        patch.object(business, 'expose', return_value=10003))
                    stack.enter_context(
                        patch.object(business, 'command', side_effect=run))
                    stack.enter_context(patch.object(business.socket,
                                                     'socket'))
                    stack.enter_context(
                        patch.object(business.business_mail,
                                     'start',
                                     side_effect=start_mail))
                    stack.enter_context(
                        patch.object(business.business_mail, 'assert_empty'))
                    stack.enter_context(
                        patch.object(business.woocommerce_fixture,
                                     'folder',
                                     return_value=Path(directory) / 'missing'))
                    stack.enter_context(
                        patch.object(travel_video, 'serve', original_tools))
                    with business.serve(task, str(work)):
                        self.assertEqual(observed, {
                            'task': task,
                            'config': str(remote)
                        })
                    self.assertEqual(os.environ['BUSINESS_TASK'],
                                     'previous-task')
                    self.assertEqual(os.environ['BUSINESS_EMAIL_CONFIG'],
                                     str(stale))
            finally:
                for artifact in artifacts:
                    artifact.unlink(missing_ok=True)


class EmailIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mail_context = greenmail()
        cls.mail = cls.mail_context.__enter__()
        cls.addClassCleanup(cls.mail_context.__exit__, None, None, None)
        cls.daemon_context = mirage_daemon()
        cls.daemon_context.__enter__()
        cls.addClassCleanup(cls.daemon_context.__exit__, None, None, None)

    def setUp(self):
        state = REPO / 'state'
        state.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='email-cli-', dir=state)
        self.work = Path(self.temp.name)
        self.saved = {
            key: os.environ.get(key)
            for key in ('AGENT_WORKSPACE', 'WHEELS_DIR', 'BUSINESS_TASK',
                        'BUSINESS_EMAIL_CONFIG')
        }
        os.environ.update(AGENT_WORKSPACE=str(self.work),
                          WHEELS_DIR=str(REPO / 'vendor/wheels'))
        self.account = json.loads(
            (REPO / 'task/toolathlon/git-bug-hunt/shared/'
             'emails_config.json').read_text())
        self.account.update(imap_server='127.0.0.1',
                            imap_port=self.mail['imap'],
                            smtp_server='127.0.0.1',
                            smtp_port=self.mail['smtp'])
        self.config = self.work / 'emails_config.json'
        self.config.write_text(json.dumps(self.account))
        os.environ.update(BUSINESS_TASK='git-bug-hunt',
                          BUSINESS_EMAIL_CONFIG=str(self.config))
        fixture = self.work / 'emails.json'
        fixture.write_text(
            json.dumps([{
                'subject':
                f'Email {index}',
                'from_addr':
                f'sender{index}@example.com',
                'body_text':
                f'body {index}',
                'attachments': ([{
                    'filename': 'fixture.txt',
                    'content_type': 'text/plain',
                    'content': 'Zml4dHVyZSBieXRlcw=='
                }] if index == 1 else [])
            } for index in range(1, 5)]))
        reset(self.mail['api'])
        fill(self.config, fixture, api=self.mail['api'], do_reset=False)
        self.bridge = serve_tools(['emails'], str(self.work), 'git-bug-hunt')
        self.bridge.__enter__()
        self.url = os.environ['EMAILS_CLI_URL']
        self.workspace_config = self.work / 'workspace.yaml'
        self.workspace_config.write_text(
            yaml.safe_dump(
                {
                    'mode': 'EXEC',
                    'runtimes': ['workspace'],
                    'clis': {
                        'emails': {
                            'cli': str(REPO / 'cli/toolathlon/emails.mjs') +
                            ':EMAILS',
                            'config': {
                                'apiBase': '${EMAILS_CLI_URL}',
                                'timeoutMs': 120000
                            }
                        }
                    },
                    'mounts': {
                        '/workspace': {
                            'vfs': 'disk',
                            'config': {
                                'root': str(self.work)
                            }
                        },
                        '/tmp': {
                            'vfs': 'ram'
                        },
                        '/mail': {
                            'vfs': 'email',
                            'config': {
                                'imapHost': '127.0.0.1',
                                'imapPort': self.mail['imap'],
                                'smtpHost': '127.0.0.1',
                                'smtpPort': self.mail['smtp'],
                                'username': self.account['email'],
                                'password': self.account['password'],
                                'useSsl': False
                            }
                        }
                    }
                },
                sort_keys=False))

    def tearDown(self):
        self.bridge.__exit__(None, None, None)
        reset(self.mail['api'])
        self.temp.cleanup()
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def call(self, name, **arguments):
        response = requests.post(self.url + '/call',
                                 json={
                                     'name': name,
                                     'arguments': arguments
                                 },
                                 timeout=120)
        response.raise_for_status()
        result = response.json()
        self.assertFalse(result.get('isError'))
        return result['content'][0]['text']

    def cli(self, workspace, name, **arguments):
        return workspace.execute('emails ' + name + ' ' +
                                 shlex.quote(json.dumps(arguments))).strip()

    def assert_fetch_refreshes_seen_flag(self, name, uid, **arguments):
        workspace = Workspace.create(self.workspace_config)
        try:
            path = workspace.execute(
                f"find /mail/INBOX -name '*__{uid}.email.json'").strip()
            self.assertTrue(path)
            before = json.loads(workspace.execute('cat ' + shlex.quote(path)))
            self.assertNotIn('\\Seen', before['flags'])
            self.assertNotIn('Error', self.cli(workspace, name, **arguments))
            after = json.loads(workspace.execute('cat ' + shlex.quote(path)))
            self.assertIn('\\Seen', after['flags'])
        finally:
            workspace.close()

    def test_a_session_idle_past_greenmails_own_timeout_still_reads(self):
        # GreenMail drops a session after 30 idle seconds unless the service's
        # entrypoint raises the limit, and setUp's reset rebuilds its servers,
        # so this is a session opened after a reset, as a model's is.
        imap = imaplib.IMAP4('127.0.0.1', self.mail['imap'])
        imap.login(self.account['email'], self.account['password'])
        imap.select('INBOX')
        time.sleep(35)
        status, _ = imap.fetch(b'1', '(BODY.PEEK[HEADER.FIELDS (SUBJECT)])')
        self.assertEqual(status, 'OK')
        imap.logout()

    def test_submitted_mail_gets_the_headers_posteio_adds(self):
        # emails-mcp sends with neither header; poste.io's Haraka adds both
        # to the delivered copy, and meeting-assign's grader parses its
        # `Date`. The copy emails-mcp appends to Sent over IMAP keeps
        # neither, as poste.io's Dovecot stores an APPEND unchanged. setUp's
        # reset rebuilt GreenMail's user manager, so this is the handler
        # `start()` installed again.
        self.call('send_email',
                  to=self.account['email'],
                  subject='Header probe',
                  body='probe')
        imap = imaplib.IMAP4('127.0.0.1', self.mail['imap'])
        imap.login(self.account['email'], self.account['password'])
        copies = {}
        for folder in ('INBOX', 'Sent'):
            imap.select(folder)
            _, found = imap.search(None, 'SUBJECT', '"Header probe"')
            _, data = imap.fetch(found[0].split()[-1], '(BODY.PEEK[HEADER])')
            copies[folder] = email.message_from_bytes(data[0][1])
        imap.logout()
        headers = copies['INBOX']
        self.assertRegex(headers['Message-Id'],
                         r'^<[0-9A-F-]{36}\.1@mail\.example\.com>$')
        self.assertRegex(
            headers['Date'], r'^\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} '
            r'[+-]\d{4}$')
        email.utils.parsedate_to_datetime(headers['Date'])
        self.assertIsNone(copies['Sent']['Message-Id'])
        self.assertIsNone(copies['Sent']['Date'])

    def test_the_models_own_mailbox_gets_posteio_folders(self):
        # landing-task-reminder has no involved_emails.json and loads no
        # fixture, so only its own mailbox config names the account.
        from server.seed import seed_task
        account = json.loads(
            (REPO / 'task/toolathlon/landing-task-reminder/shared/'
             'emails_config.json').read_text())
        account.update(imap_server='127.0.0.1', imap_port=self.mail['imap'])
        local = self.work / 'landing-task-reminder'
        (local / 'shared').mkdir(parents=True)
        (local / 'shared/emails_config.json').write_text(json.dumps(account))
        with patch.dict(os.environ, MAIL_API_PORT=str(
                self.mail['api_port'])), patch.object(seed_task.dataset,
                                                      'local',
                                                      return_value=local):
            seed_task.seed_mail('landing-task-reminder',
                                {'id': 'mail/' + account['email']})
        imap = imaplib.IMAP4('127.0.0.1', self.mail['imap'])
        imap.login(account['email'], account['password'])
        _, listed = imap.list()
        imap.logout()
        names = {
            line.decode().rsplit(' ', 1)[-1].strip('"')
            for line in listed
        }
        self.assertLessEqual({'INBOX', 'Sent', 'Drafts', 'Trash'}, names)

    def test_exact_catalog_and_single_and_batch_mutations(self):
        live = requests.get(self.url + '/tools', timeout=15).json()
        captured = json.loads(
            (REPO / 'vendor/emails-mcp/tools.json').read_text())
        self.assertEqual(live, captured)

        self.assertIn('Total emails: 4', self.call('get_emails'))
        self.assertIn('created successfully',
                      self.call('create_folder', folder_name='Archive'))
        self.assertEqual(
            self.call('move_email', email_id='4', target_folder='Archive'),
            'Email 4 moved to Archive successfully')
        self.assertEqual(self.call('delete_email', email_id='3'),
                         'Email 3 deleted successfully')
        self.assertEqual(
            self.call('move_emails',
                      email_ids=['1', '2'],
                      target_folder='Archive'),
            'Successfully moved 2/2 emails to Archive')
        self.assertIn("Folder 'INBOX' is empty", self.call('get_emails'))
        self.assertIn('Total emails: 3',
                      self.call('get_emails', folder='Archive'))
        self.assertEqual(self.call('delete_emails', email_ids=['1', '2', '3']),
                         'Successfully deleted 3/3 emails')
        self.assertIn("Folder 'Archive' is empty",
                      self.call('get_emails', folder='Archive'))

    def test_cli_mutation_invalidates_the_mail_mount(self):
        workspace = Workspace.create(self.workspace_config)
        try:
            self.assertIn('Total emails: 4',
                          workspace.execute("emails get_emails '{}'"))
            before = workspace.execute(
                "find /mail/INBOX -name '*.email.json' | wc -l").strip()
            self.assertEqual(before, '4')
            self.assertEqual(
                workspace.execute(
                    "emails delete_email '{\"email_id\":\"4\"}'").strip(),
                'Email 4 deleted successfully')
            after = workspace.execute(
                "find /mail/INBOX -name '*.email.json' | wc -l").strip()
            self.assertEqual(after, '3')
        finally:
            workspace.close()

    def test_listing_refreshes_cached_seen_flags(self):
        self.assert_fetch_refreshes_seen_flag('get_emails',
                                              '4',
                                              folder='INBOX',
                                              page_size=1)

    def test_search_refreshes_cached_seen_flags(self):
        self.assert_fetch_refreshes_seen_flag('search_emails',
                                              '1',
                                              query='Email 1',
                                              folder='INBOX')

    def test_headers_refresh_cached_seen_flags(self):
        # This upstream operation omits a folder argument and therefore
        # requires an already selected mailbox on its persistent connection.
        # An empty search selects INBOX without fetching or marking a message.
        self.call('search_emails',
                  query='definitely-no-such-message',
                  folder='INBOX')
        self.assert_fetch_refreshes_seen_flag('get_email_headers',
                                              '1',
                                              email_id='1')

    def test_disk_workspace_file_round_trips(self):
        self.disk_workspace_file_round_trips('/workspace')

    def test_course_workspace_file_round_trips(self):
        self.bridge.__exit__(None, None, None)
        os.environ['BUSINESS_TASK'] = 'course-assistant'
        self.bridge = serve_tools(['emails'], str(self.work),
                                  'course-assistant')
        self.bridge.__enter__()
        self.url = os.environ['EMAILS_CLI_URL']
        config = yaml.safe_load(self.workspace_config.read_text())
        self.workspace_config.write_text(yaml.safe_dump(config))
        self.disk_workspace_file_round_trips('/workspace')

    def disk_workspace_file_round_trips(self, virtual_root):
        workspace = Workspace.create(self.workspace_config)
        try:
            workspace.execute(
                f"printf 'shared attachment' > {virtual_root}/upload.txt")
            sent = self.cli(workspace,
                            'send_email',
                            to=self.account['email'],
                            subject='Shared workspace round trip',
                            body='attachment follows',
                            attachments=[virtual_root + '/upload.txt'])
            self.assertIn('with 1 attachments', sent)
            found = self.cli(workspace,
                             'search_emails',
                             query='Shared workspace round trip',
                             folder='INBOX')
            email_id = re.search(r'ID: (\d+)', found).group(1)
            downloaded = self.cli(workspace,
                                  'download_attachment',
                                  email_id=email_id,
                                  attachment_filename='upload.txt')
            self.assertIn(virtual_root + '/emails_download/', downloaded)
            self.assertEqual(
                workspace.execute('cat ' + virtual_root +
                                  '/emails_download/upload.txt').strip(),
                'shared attachment')

            exported = self.cli(workspace, 'export_emails', folder='INBOX')
            export_path = re.search(
                '(' + re.escape(virtual_root) + r'/\S+\.json)',
                exported).group(1)
            payload = json.loads(
                workspace.execute('cat ' + shlex.quote(export_path)))
            self.assertGreaterEqual(payload['total_emails'], 5)
            self.assertIn(
                'created successfully',
                self.cli(workspace, 'create_folder', folder_name='Imported'))
            imported = self.cli(workspace,
                                'import_emails',
                                import_path=export_path,
                                target_folder='Imported',
                                preserve_folders=False)
            self.assertRegex(imported,
                             r'Successfully imported [1-9]\d*/[1-9]\d*')
        finally:
            workspace.close()

    def test_fastmcp_rejects_invalid_attachment_types(self):
        for attachments in ('/workspace/upload.txt', [7]):
            with self.subTest(attachments=attachments):
                response = requests.post(self.url + '/call',
                                         json={
                                             'name': 'send_email',
                                             'arguments': {
                                                 'to': self.account['email'],
                                                 'subject': 'invalid',
                                                 'body': 'invalid',
                                                 'attachments': attachments
                                             }
                                         },
                                         timeout=120)
                response.raise_for_status()
                self.assertTrue(response.json().get('isError'))


if __name__ == '__main__':
    unittest.main()
