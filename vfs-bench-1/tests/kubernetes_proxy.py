"""Exercise real kubectl proxy authentication and private-state cleanup."""
import base64
import ipaddress
import json
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import urlopen

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server.kubernetes_proxy import serve  # noqa: E402


class KubernetesProxy(unittest.TestCase):

    def test_authentication_and_cleanup_on_success_and_failure(self):
        # A local mTLS server proves credentials are used only upstream.
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(
            name).public_key(key.public_key()).serial_number(
                x509.random_serial_number()).not_valid_before(now - timedelta(
                    minutes=1)).not_valid_after(now + timedelta(
                        hours=1)).add_extension(
                            x509.SubjectAlternativeName([
                                x509.IPAddress(
                                    ipaddress.ip_address('127.0.0.1'))
                            ]),
                            critical=False).add_extension(
                                x509.BasicConstraints(ca=True,
                                                      path_length=None),
                                critical=True).sign(
                                    key, hashes.SHA256())).public_bytes(
                                        serialization.Encoding.PEM)
        pem = key.private_bytes(serialization.Encoding.PEM,
                                serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        requests = []

        class Handler(BaseHTTPRequestHandler):

            def do_GET(self):
                requests.append((self.path, self.connection.getpeercert()))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"kind":"NamespaceList","items":[]}')

            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / 'cert.pem').write_bytes(cert)
            (root / 'key.pem').write_bytes(pem)
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(root / 'cert.pem', root / 'key.pem')
            tls.load_verify_locations(cadata=cert.decode())
            tls.verify_mode = ssl.CERT_REQUIRED
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            server.socket = tls.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(thread.join, 3)
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            config = {
                'apiVersion':
                'v1',
                'kind':
                'Config',
                'current-context':
                'local',
                'contexts': [{
                    'name': 'local',
                    'context': {
                        'cluster': 'local',
                        'user': 'local'
                    }
                }],
                'clusters': [{
                    'name': 'local',
                    'cluster': {
                        'server':
                        f'https://127.0.0.1:{server.server_port}',
                        'certificate-authority-data':
                        base64.b64encode(cert).decode()
                    }
                }],
                'users': [{
                    'name': 'local',
                    'user': {
                        'client-certificate-data':
                        base64.b64encode(cert).decode(),
                        'client-key-data': base64.b64encode(pem).decode()
                    }
                }],
            }
            binary = REPO / 'vendor/kubernetes-bin/kubectl'
            with patch('tempfile.tempdir', scratch):
                for fail in (False, True):
                    try:
                        with serve(config, binary) as public:
                            self.assertEqual(public['users'][0]['user'], {})
                            self.assertEqual(
                                set(public['clusters'][0]['cluster']),
                                {'server', 'insecure-skip-tls-verify'})
                            self.assertNotIn(
                                base64.b64encode(pem).decode(),
                                json.dumps(public))
                            self.assertNotIn(
                                base64.b64encode(cert).decode(),
                                json.dumps(public))
                            private, = root.glob(
                                'kubernetes-auth-*/config.yaml')
                            self.assertEqual(private.stat().st_mode & 0o777,
                                             0o600)
                            url = public['clusters'][0]['cluster'][
                                'server'] + '/api/v1/namespaces'
                            with urlopen(url, timeout=5) as response:
                                self.assertEqual(
                                    json.load(response)['kind'],
                                    'NamespaceList')
                            self.assertTrue(requests[-1][1])
                            # The pinned MCP uses client-node for pod exec;
                            # unlike kubectl, it explicitly opts into HTTP.
                            sdk = (REPO / 'vendor/kubernetes-mcp/node_modules/'
                                   '@kubernetes/client-node/dist/index.js')
                            script = (
                                'import { KubeConfig, CoreV1Api } from ' +
                                json.dumps(sdk.as_uri()) + ';'
                                'const config = new KubeConfig();'
                                'config.loadFromString(process.argv[1]);'
                                'const result = await config.makeApiClient('
                                'CoreV1Api).listNamespace();'
                                'process.stdout.write(result.kind);')
                            checked = subprocess.run([
                                'node', '--input-type=module', '-e', script,
                                json.dumps(public)
                            ],
                                                     capture_output=True,
                                                     text=True,
                                                     timeout=10)
                            self.assertEqual(checked.returncode, 0,
                                             checked.stderr)
                            self.assertEqual(checked.stdout, 'NamespaceList')
                            self.assertTrue(requests[-1][1])
                            if fail:
                                raise ValueError('fixture caller failed')
                    except ValueError as error:
                        self.assertTrue(fail)
                        self.assertEqual(str(error), 'fixture caller failed')
                    self.assertFalse(list(root.glob('kubernetes-auth-*')))
                    with self.assertRaises(URLError):
                        urlopen(url, timeout=1)
                with self.assertRaisesRegex(RuntimeError, 'proxy exited'):
                    with serve(config, Path('/usr/bin/false')):
                        self.fail('failed proxy must not yield')
                self.assertFalse(list(root.glob('kubernetes-auth-*')))


if __name__ == '__main__':
    unittest.main()
