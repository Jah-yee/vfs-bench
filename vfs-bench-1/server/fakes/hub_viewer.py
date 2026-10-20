import gzip
import hashlib
import http.server
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# The one tool whose Dataset Viewer operations mirage's Hub fake refuses,
# and which the live server was asked instead. Everything else that reaches
# this proxy is handed to the fake untouched.
TOOL = 'hub_repo_details'
DEFAULTS = {'offset': 0, 'limit': 5}


def folder(task: str) -> Path:
    return REPO / 'task/toolathlon' / task / 'shared/hub-viewer'


def load(task: str) -> dict:
    """The captured live responses, once the receipt's hash still holds."""
    receipt = json.loads((folder(task) / 'source.json').read_text())
    data = (folder(task) / 'responses.json.gz').read_bytes()
    if hashlib.sha256(
            data).hexdigest() != receipt['sha256']['responses.json.gz']:
        raise ValueError(f'{task}: Hub viewer capture checksum mismatch')
    return json.loads(gzip.decompress(data))


def key(arguments: dict) -> str:
    """One exact request, with the two defaults the tool document states.

    `offset` "Defaults to 0" and `limit` "Defaults to 5" in the captured
    tool document, so a call that leaves them out and one that spells them
    is the same request to the live server. Nothing else is normalized: the
    live server renders a different document for a different operation
    list, so the list is matched as given.
    """
    spelled = {**DEFAULTS, **arguments}
    return json.dumps(spelled, sort_keys=True, ensure_ascii=False)


class Handler(http.server.BaseHTTPRequestHandler):
    upstream = ''
    captured: dict[str, dict] = {}

    def log_message(self, *_):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        reply = self.replay(body)
        if reply is None:
            return self.forward(body)
        # The fake answers every POST as one SSE message, so a replayed
        # answer is framed the same way and a client cannot tell them apart.
        payload = ('event: message\ndata: ' +
                   json.dumps(reply, ensure_ascii=False) + '\n\n').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.forward(None)

    def do_DELETE(self):
        self.forward(None)

    def replay(self, body: bytes):
        try:
            message = json.loads(body)
        except ValueError:
            return None
        if not isinstance(message,
                          dict) or message.get('method') != 'tools/call':
            return None
        params = message.get('params') or {}
        if params.get('name') != TOOL:
            return None
        found = self.captured.get(key(params.get('arguments') or {}))
        if found is None:
            return None
        return {'jsonrpc': '2.0', 'id': message.get('id'), 'result': found}

    def forward(self, body):
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in ('host', 'content-length')
        }
        request = urllib.request.Request(self.upstream + self.path,
                                         data=body,
                                         headers=headers,
                                         method=self.command)
        try:
            response = urllib.request.urlopen(request, timeout=300)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            self.send_response(response.status)
            content = response.read()
            for name, value in response.headers.items():
                if name.lower() not in ('transfer-encoding', 'content-length',
                                        'connection'):
                    self.send_header(name, value)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)


def start(task: str, upstream: str):
    """A proxy in front of `upstream` answering captured viewer requests."""
    captured = {
        key(item['arguments']): item['result']
        for item in load(task)['responses']
    }
    parts = urllib.parse.urlsplit(upstream)
    handler = type('Handler', (Handler, ), {
        'upstream': f'{parts.scheme}://{parts.netloc}',
        'captured': captured
    })
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{server.server_port}{parts.path}'


@contextmanager
def serve(task: str):
    """Put the captured Dataset Viewer answers in front of the Hub fake.

    Both arms read the Hub MCP endpoint named by `HF_MCP_URL` -- upstream's
    `mcp-remote` bridge on one side, the `huggingface` CLI on the other -- so
    the variable is repointed here for both and restored after.
    """
    upstream = os.environ.get('HF_MCP_URL', 'http://127.0.0.1:5200/mcp')
    server, url = start(task, upstream)
    previous = os.environ.get('HF_MCP_URL')
    os.environ['HF_MCP_URL'] = url
    try:
        yield url
    finally:
        if previous is None:
            os.environ.pop('HF_MCP_URL', None)
        else:
            os.environ['HF_MCP_URL'] = previous
        server.shutdown()
        server.server_close()
