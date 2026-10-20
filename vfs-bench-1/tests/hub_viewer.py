import gzip
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server.fakes import hub_viewer  # noqa: E402

FRAME = 'event: message\ndata: {}\n\n'


class Fake(http.server.BaseHTTPRequestHandler):
    """Stands in for mirage's Hub MCP fake: one SSE message per POST."""
    seen = []

    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(
            self.rfile.read(int(self.headers.get('Content-Length') or 0)))
        self.seen.append((self.path, dict(self.headers), body))
        reply = {
            'jsonrpc': '2.0',
            'id': body.get('id'),
            'result': {
                'content': [{
                    'type': 'text',
                    'text': 'fake: ' + json.dumps(body.get('params'))
                }]
            }
        }
        payload = FRAME.format(json.dumps(reply)).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.send_response(405)
        self.end_headers()


def post(url, body, headers=None):
    request = urllib.request.Request(url,
                                     data=json.dumps(body).encode(),
                                     headers={
                                         'Content-Type': 'application/json',
                                         **(headers or {})
                                     },
                                     method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        text = response.read().decode()
    line = next(line for line in text.splitlines() if line.startswith('data:'))
    return json.loads(line[len('data:'):])


def call(arguments, ident=7):
    return {
        'jsonrpc': '2.0',
        'id': ident,
        'method': 'tools/call',
        'params': {
            'name': hub_viewer.TOOL,
            'arguments': arguments
        }
    }


class HubViewer(unittest.TestCase):

    def setUp(self):
        Fake.seen = []
        self.fake = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fake)
        threading.Thread(target=self.fake.serve_forever, daemon=True).start()
        self.addCleanup(self.fake.server_close)
        self.addCleanup(self.fake.shutdown)
        self.upstream = f'http://127.0.0.1:{self.fake.server_port}/mcp'
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        captured = {
            'task':
            't',
            'revisions': {},
            'responses': [{
                'arguments': {
                    'repo_ids': ['o/d'],
                    'operations': ['dataset_structure']
                },
                'result': {
                    'content': [{
                        'type': 'text',
                        'text': '## Dataset Structure (live)'
                    }]
                }
            }, {
                'arguments': {
                    'repo_ids': ['o/d'],
                    'operations': ['dataset_preview'],
                    'config': 'default',
                    'split': 'train',
                    'offset': 5,
                    'limit': 5
                },
                'result': {
                    'content': [{
                        'type': 'text',
                        'text': '## Dataset Preview rows 5-9 (live)'
                    }]
                }
            }]
        }
        folder = Path(self.tmp.name) / 't'
        folder.mkdir()
        data = gzip.compress(json.dumps(captured).encode())
        (folder / 'responses.json.gz').write_bytes(data)
        (folder / 'source.json').write_text(
            json.dumps({
                'sha256': {
                    'responses.json.gz': hashlib.sha256(data).hexdigest()
                }
            }))
        patcher = patch.object(hub_viewer, 'folder', lambda task: folder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_captured_requests_are_answered_and_the_rest_forwarded(self):
        with patch.dict(os.environ, {'HF_MCP_URL': self.upstream}):
            with hub_viewer.serve('t') as url:
                self.assertEqual(os.environ['HF_MCP_URL'], url)
                self.assertNotEqual(url, self.upstream)
                # An exact captured request, and the same one with the
                # tool document's defaults spelled out.
                reply = post(
                    url,
                    call({
                        'repo_ids': ['o/d'],
                        'operations': ['dataset_structure']
                    }))
                self.assertEqual(reply['id'], 7)
                self.assertEqual(reply['result']['content'][0]['text'],
                                 '## Dataset Structure (live)')
                reply = post(
                    url,
                    call(
                        {
                            'repo_ids': ['o/d'],
                            'operations': ['dataset_structure'],
                            'offset': 0,
                            'limit': 5
                        }, 8))
                self.assertEqual(reply['id'], 8)
                self.assertEqual(reply['result']['content'][0]['text'],
                                 '## Dataset Structure (live)')
                # A page nobody captured, another tool, and a listing all
                # reach the fake with their headers.
                for body in (call({
                        'repo_ids': ['o/d'],
                        'operations': ['dataset_preview'],
                        'config': 'default',
                        'split': 'train',
                        'offset': 15
                }), {
                        'jsonrpc': '2.0',
                        'id': 9,
                        'method': 'tools/call',
                        'params': {
                            'name': 'hf_fs',
                            'arguments': {}
                        }
                }, {
                        'jsonrpc': '2.0',
                        'id': 10,
                        'method': 'tools/list'
                }):
                    reply = post(url, body, {'Authorization': 'Bearer t'})
                    self.assertTrue(reply['result']['content'][0]
                                    ['text'].startswith('fake: '))
                self.assertEqual(len(Fake.seen), 3)
                for path, headers, _ in Fake.seen:
                    self.assertEqual(path, '/mcp')
                    self.assertEqual(headers['Authorization'], 'Bearer t')
            self.assertEqual(os.environ['HF_MCP_URL'], self.upstream)

    def test_a_tampered_capture_is_refused(self):
        folder = hub_viewer.folder('t')
        (folder / 'responses.json.gz').write_bytes(
            gzip.compress(b'{"responses": []}'))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            hub_viewer.load('t')


if __name__ == '__main__':
    unittest.main()
