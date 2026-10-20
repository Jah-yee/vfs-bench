import base64
import hashlib
import json
import os
import selectors
import subprocess
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

import requests

ORIGINS = {
    '/maps/': 'https://maps.googleapis.com/',
    '/youtube/': 'https://youtube.googleapis.com/youtube/',
    '/rail/': 'https://kyfw.12306.cn/',
    '/rail-search/': 'https://search.12306.cn/',
    '/rail-web/': 'https://www.12306.cn/',
    '/api/v3/': 'https://api.github.com/',
    '/api/graphql': 'https://api.github.com/graphql',
}


@contextmanager
def railway_http():
    # Foreign runtime: using Node's original locked axios transport is needed
    # for 12306, whose edge rejects the Python requests client on some routes.
    from server.seed.papers import close
    process = subprocess.Popen([
        'node',
        str(Path(__file__).resolve().parents[1] / 'clients/rail_http.mjs')
    ],
                               stdout=subprocess.PIPE,
                               text=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=30):
                raise RuntimeError('Railway HTTP transport did not start')
            endpoint = process.stdout.readline().strip()
        if not endpoint.startswith('http://127.0.0.1:'):
            raise RuntimeError('Railway HTTP transport failed')
        yield endpoint
    finally:
        close(process)


@contextmanager
def serve(*, railway=False):
    """Serve the public APIs the final tasks read, live on both arms.

    Every request is read live each time it is asked for, and nothing a
    run fetches is kept.
    """
    from server.seed.research import encode
    records = []

    class Handler(BaseHTTPRequestHandler):

        # The original railway fetch reads cookie headers without consuming
        # the page body. Closing an HTTP/1.0 response can crash Node's parser.
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            if self.path == '/yahoo/sdk':
                body = self.rfile.read(int(self.headers['Content-Length']))
                result = requests.post(os.environ['YAHOO_CLI_URL'] + '/sdk',
                                       data=body,
                                       headers={
                                           'Content-Type': 'application/json'
                                       },
                                       timeout=120).json()
                receipt = result.pop('snapshot', None)
                if receipt:
                    records.append({'kind': 'yahoo', **receipt})
                data = json.dumps(result).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.respond()

        def respond(self):
            prefix = next(
                (prefix for prefix in ORIGINS if self.path.startswith(prefix)),
                None)
            if prefix is None:
                self.send_error(404)
                return
            if prefix == '/api/v3/' and self.command != 'GET':
                self.send_error(
                    403, 'This original task has read-only GitHub access')
                return
            target = ORIGINS[prefix] + self.path[len(prefix):]
            parsed = urlsplit(target)
            query = [(key, value)
                     for key, value in parse_qsl(parsed.query,
                                                 keep_blank_values=True)
                     if key.lower() not in ('key', 'api_key', 'access_token')]
            public_target = parsed._replace(query=urlencode(query)).geturl()
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            if prefix == '/api/graphql':
                # Original read-only tools send one anonymous query. Multiple
                # operations require operationName, which is not needed here.
                value = json.loads(body)
                query_text = value.get('query', '').lstrip()
                if (self.command != 'POST' or value.get('operationName')
                        or not query_text.startswith(('query', '{'))):
                    self.send_error(403, 'Read-only GitHub queries only')
                    return
            headers = {
                key: self.headers[key]
                for key in ('Accept', 'Accept-Language', 'Content-Type',
                            'User-Agent', 'Cookie', 'X-GitHub-Api-Version')
                if key in self.headers
            }
            request = {
                'method': self.command,
                'url': public_target,
                # Fresh anonymous session cookies authorize a read; they do
                # not identify its task data or belong in capture receipts.
                'headers': {
                    k: v
                    for k, v in headers.items() if k != 'Cookie'
                },
                'body': base64.b64encode(body).decode()
            }
            is_railway = prefix in ('/rail/', '/rail-search/', '/rail-web/')
            bootstrap = is_railway and parsed.path.endswith('/init')

            def fetch():
                actual = list(query)
                if prefix in ('/maps/', '/youtube/'):
                    key = ('GOOGLE_MAPS_API_KEY'
                           if prefix == '/maps/' else 'YOUTUBE_API_KEY')
                    actual.append(('key', os.environ[key]))
                outgoing = dict(headers)
                if prefix in ('/api/v3/', '/api/graphql') and os.environ.get(
                        'GITHUB_PERSONAL_ACCESS_TOKEN'):
                    outgoing['Authorization'] = 'Bearer ' + os.environ[
                        'GITHUB_PERSONAL_ACCESS_TOKEN']
                url = parsed._replace(query=urlencode(actual)).geturl()
                if is_railway:
                    if rail_http is None or self.command != 'GET':
                        raise ValueError(
                            'Railway read transport is unavailable')
                    response = requests.post(rail_http,
                                             json={
                                                 'url': url,
                                                 'headers': outgoing
                                             },
                                             timeout=95)
                    response.raise_for_status()
                    result = response.json()
                    data = base64.b64decode(result['body'])
                    success = 200 <= result['status'] < 400
                    is_json = not parsed.path.endswith(('.js', '/'))
                    if not bootstrap and is_json:
                        try:
                            value = json.loads(data)
                            success = (success and isinstance(value, dict)
                                       and value.get('status') is not False)
                        except ValueError:
                            success = False
                    return result, success
                response = requests.request(self.command,
                                            url,
                                            headers=outgoing,
                                            data=body or None,
                                            timeout=90)
                # requests has already decoded transfer encoding.
                response_headers = {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() not in ('content-encoding',
                                           'transfer-encoding',
                                           'content-length', 'connection',
                                           'set-cookie')
                }
                # The railway server calls getSetCookie(); joining these with
                # commas would change both cookie parsing and later requests.
                cookies = response.raw.headers.getlist('Set-Cookie')
                data = response.content
                result = {
                    'status': response.status_code,
                    'headers': response_headers,
                    'cookies': cookies,
                    'body': base64.b64encode(data).decode()
                }
                success = (response.ok and b'REQUEST_DENIED' not in data
                           and b'OVER_QUERY_LIMIT' not in data)
                return result, success

            try:
                result, _ = fetch()
                records.append({
                    'kind':
                    'public-services',
                    'source':
                    'live',
                    'request':
                    request,
                    'fetched_at':
                    datetime.now(timezone.utc).isoformat(),
                    'response_sha256':
                    hashlib.sha256(encode(result)).hexdigest()
                })
                data = base64.b64decode(result['body'])
                self.send_response(result['status'])
                for key, value in result['headers'].items():
                    self.send_header(key, value)
                for cookie in result.get('cookies', []):
                    self.send_header('Set-Cookie', cookie)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                # SDK request exceptions can embed credentials in request URLs.
                self.send_error(502, 'Public service request failed')

    with ExitStack() as stack:
        rail_http = stack.enter_context(railway_http()) if railway else None
        from server.execution import background
        with background(Handler) as url:
            yield url, records
