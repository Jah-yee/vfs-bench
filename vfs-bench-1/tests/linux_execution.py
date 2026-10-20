"""Linux native boundary: real processes and sockets, no mocked sandbox.

Run on Linux 6.12+ after `python -m server.linux_sandbox`. Container hosts
must permit Sandlock's pidfd_getfd/process_vm_readv supervision syscalls.
"""
import errno
import http.server
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server.execution import launch  # noqa: E402


@unittest.skipUnless(sys.platform in ('darwin', 'linux'),
                     'requires native confinement')
class RuntimeScratch(unittest.TestCase):

    def test_launcher_defaults_to_accessible_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / 'work'
            work.mkdir()
            params = launch(
                {
                    'command': sys.executable,
                    'args': ['-c', 'import os; print(os.getcwd())'],
                }, work)
            result = subprocess.run([params['command'], *params['args']],
                                    cwd=params['cwd'],
                                    env=params['env'],
                                    capture_output=True,
                                    text=True,
                                    timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                Path(result.stdout.strip()).resolve(), work.resolve())

    def test_caches_do_not_pollute_workspace_or_cross_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / 'first', root / 'second'
            first.mkdir()
            second.mkdir()
            params = launch({
                'command': sys.executable,
                'env': os.environ
            }, first)
            other = launch({
                'command': sys.executable,
                'env': os.environ
            }, second)
            scratch = Path(params['env']['TMPDIR'])
            secret = Path(other['env']['TMPDIR']) / 'other-run'
            secret.write_text('private')
            code = f"""
import os
from pathlib import Path
Path(os.environ['TMPDIR'], 'excel-mcp.log').write_text('log')
cache = Path(os.environ['UV_CACHE_DIR'])
cache.mkdir()
(cache / 'entry').write_text('cache')
try:
    Path({str(secret)!r}).read_text()
except PermissionError:
    pass
else:
    raise AssertionError('another run scratch was readable')
"""
            result = subprocess.run(
                [params['command'], *params['args'], '-c', code],
                env=params['env'],
                cwd=first,
                capture_output=True,
                text=True,
                timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(scratch.is_relative_to(first))
            self.assertEqual((scratch / 'excel-mcp.log').read_text(), 'log')
            self.assertEqual(list(first.iterdir()), [])
            self.assertEqual(list(second.iterdir()), [])


@unittest.skipUnless(sys.platform == 'linux',
                     'requires real Linux confinement')
class LinuxExecution(unittest.TestCase):

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name) / 'work'
        self.work.mkdir()
        self.secret = self.work.parent / 'secret'
        self.secret.write_text('outside sentinel')

    def command(self, argv):
        params = launch(
            {
                'command': argv[0],
                'args': argv[1:],
                'env': os.environ
            }, self.work)
        return subprocess.run([params['command'], *params['args']],
                              cwd=self.work,
                              env=params['env'],
                              input='stdin sentinel',
                              text=True,
                              capture_output=True,
                              timeout=20)

    def python(self, code):
        result = self.command([sys.executable, '-c', code])
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_native_io_and_filesystem_boundary(self):
        output = self.python(f"""
import os, sys
from pathlib import Path
assert Path.cwd() == Path({str(self.work)!r})
Path('answer.txt').write_text(sys.stdin.read())
assert Path('answer.txt').read_text() == 'stdin sentinel'
for mode in ('r', 'w'):
    try:
        open({str(self.secret)!r}, mode)
    except PermissionError:
        pass
    else:
        raise AssertionError('outside file access succeeded: ' + mode)
print('native io works')
""")
        self.assertEqual(output, 'native io works')
        self.assertEqual(self.secret.read_text(), 'outside sentinel')
        self.assertEqual((self.work / 'answer.txt').read_text(),
                         'stdin sentinel')

    def test_host_loopback_tcp_and_udp(self):
        for family, address in ((socket.AF_INET, '127.0.0.1'),
                                (socket.AF_INET6, '::1')):
            for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
                with self.subTest(address=address, kind=kind):
                    with socket.socket(family, kind) as server:
                        server.settimeout(10)
                        server.bind((address, 0))
                        port = server.getsockname()[1]
                        if kind == socket.SOCK_STREAM:
                            server.listen()

                        def reply():
                            if kind == socket.SOCK_STREAM:
                                conn, _ = server.accept()
                                with conn:
                                    conn.sendall(conn.recv(64))
                            else:
                                body, peer = server.recvfrom(64)
                                server.sendto(body, peer)

                        worker = threading.Thread(target=reply, daemon=True)
                        worker.start()
                        try:
                            self.assertEqual(
                                self.python(f"""
import socket
with socket.socket({int(family)}, {int(kind)}) as s:
    s.settimeout(5)
    s.connect(({address!r}, {port}))
    s.sendall(b'fixture bytes')
    print(s.recv(64).decode())
"""), 'fixture bytes')
                        finally:
                            worker.join(timeout=10)
                        self.assertFalse(worker.is_alive())

    def test_confined_server_is_reachable_from_host(self):
        code = """
import socket
with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    s.listen()
    print(s.getsockname()[1], flush=True)
    conn, _ = s.accept()
    with conn:
        conn.sendall(b'callback bytes')
"""
        params = launch(
            {
                'command': sys.executable,
                'args': ['-c', code],
                'env': os.environ
            }, self.work)
        proc = subprocess.Popen([params['command'], *params['args']],
                                cwd=self.work,
                                env=params['env'],
                                text=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        try:
            import selectors
            with selectors.DefaultSelector() as ready:
                ready.register(proc.stdout, selectors.EVENT_READ)
                self.assertTrue(ready.select(10), 'server did not start')
            line = proc.stdout.readline()
            self.assertTrue(line.strip().isdigit(), line)
            with socket.create_connection(('127.0.0.1', int(line)),
                                          5) as client:
                self.assertEqual(client.recv(64), b'callback bytes')
            _, error = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, error)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.communicate(timeout=10)

    def non_loopback_address(self):
        # UDP connect selects a route without sending a packet.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
            route.connect(('192.0.2.1', 9))
            address = route.getsockname()[0]
        self.assertFalse(address.startswith('127.'))
        return address

    def test_non_loopback_syscalls_denied_against_reachable_listener(self):
        address = self.non_loopback_address()
        for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
            with self.subTest(kind=kind), socket.socket(socket.AF_INET,
                                                        kind) as server:
                server.bind(('0.0.0.0', 0))
                port = server.getsockname()[1]
                if kind == socket.SOCK_STREAM:
                    server.listen()
                server.settimeout(3)
                # Positive control: this destination is reachable outside the
                # sandbox, so a missing route cannot disguise a broken policy.
                with socket.socket(socket.AF_INET, kind) as baseline:
                    baseline.connect((address, port))
                    baseline.sendall(b'baseline')
                    if kind == socket.SOCK_STREAM:
                        conn, _ = server.accept()
                        with conn:
                            self.assertEqual(conn.recv(64), b'baseline')
                    else:
                        self.assertEqual(server.recvfrom(64)[0], b'baseline')
                self.python(f"""
import socket
for family, ip in ((socket.AF_INET, {address!r}),
                   (socket.AF_INET6, {'::ffff:' + address!r})):
    with socket.socket(family, {int(kind)}) as s:
        s.settimeout(2)
        try:
            if {int(kind)} == socket.SOCK_STREAM:
                s.connect((ip, {port}))
            else:
                s.sendto(b'blocked', (ip, {port}))
        except OSError as error:
            # Sandlock deliberately uses ECONNREFUSED for IP-policy denial.
            assert error.errno == {errno.ECONNREFUSED}, error
        else:
            raise AssertionError('non-loopback request escaped')
""")
                server.settimeout(0.1)
                with self.assertRaises(TimeoutError):
                    if kind == socket.SOCK_STREAM:
                        server.accept()
                    else:
                        server.recvfrom(64)

    def test_ping_cannot_bypass_network_policy(self):
        address = self.non_loopback_address()
        args = ['ping', '-c', '1', '-W', '1', address]
        baseline = subprocess.run(args, capture_output=True, timeout=5)
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        blocked = self.command(args)
        self.assertNotEqual(blocked.returncode, 0)
        for loopback in ('127.0.0.1', '::1'):
            allowed = self.command(['ping', '-c', '1', '-W', '1', loopback])
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_curl_proxy_bypass_and_redirects(self):

        class Fixture(http.server.BaseHTTPRequestHandler):

            def do_GET(self):
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', self.server.blocked_url)
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'fixture response')

            def log_message(self, *_args):
                pass

        with http.server.ThreadingHTTPServer(('0.0.0.0', 0),
                                             Fixture) as server:
            server.blocked_url = (f'http://{self.non_loopback_address()}:'
                                  f'{server.server_port}')
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                for program in ('curl', 'wget'):
                    args = ([
                        'curl', '--noproxy', '*', '-sS', '-L', '--max-time',
                        '3'
                    ] if program == 'curl' else [
                        'wget', '--no-proxy', '-qO-', '--timeout=3',
                        '--tries=1'
                    ])
                    allowed = self.command([*args, base])
                    self.assertEqual(allowed.returncode, 0, allowed.stderr)
                    self.assertEqual(allowed.stdout, 'fixture response')
                    for url in (base + '/redirect', server.blocked_url):
                        blocked = self.command([*args, url])
                        self.assertNotEqual(blocked.returncode, 0)
            finally:
                server.shutdown()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
