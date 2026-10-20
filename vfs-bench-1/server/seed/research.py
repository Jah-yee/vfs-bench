import asyncio
import base64
import hashlib
import importlib
import ipaddress
import json
import logging
import os
import socket
import subprocess
import tempfile
import threading
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import aiohttp
import requests

from server.seed.business import restore_environment
from server.seed.final_batch import TASKS as FINAL_TASKS
from server.seed.papers import close

REPO = Path(__file__).resolve().parents[2]
TASKS = ('verl-dataset', 'git-milestone', 'academic-pdf-report', 'add-bibtex',
         'cvpr-research', 'logical-datasets-collection',
         'profile-update-online', 'hk-top-conf', 'gdp-cr5-analysis',
         'llm-training-dataset', 'inter-final-performance-analysis',
         *FINAL_TASKS)
CURRENT = None


def redact(text):
    for key in os.environ.get('SERPER_API_KEY', '').split(','):
        if key.strip():
            text = text.replace(key.strip(), '[REDACTED]')
    return text


class SecretFilter(logging.Filter):

    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def active():
    return CURRENT


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False).encode()


def public_url(url):
    """Public fetches must not reach other tasks' local fixture services."""
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('Expected a public HTTP or HTTPS URL')
    addresses = socket.getaddrinfo(parsed.hostname,
                                   parsed.port or
                                   (443 if parsed.scheme == 'https' else 80),
                                   type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global
                            for address in addresses):
        raise ValueError(
            'Private network targets are outside the task workspace')


def now():
    return datetime.now(timezone.utc).isoformat()


def read(url, headers, allowed=public_url):
    """One live read under the original redirect rules, never kept."""
    from server.mcp.mcp_servers import timeout_for
    with requests.Session() as session:
        session.trust_env = False
        target = url
        headers = dict(headers)
        for _ in range(21):
            allowed(target)
            response = session.get(target,
                                   headers=headers,
                                   timeout=timeout_for('fetch'),
                                   allow_redirects=False)
            if not response.is_redirect:
                break
            next_url = urljoin(target, response.headers['Location'])
            if urlsplit(next_url).netloc != urlsplit(target).netloc:
                headers = {
                    key: value
                    for key, value in headers.items()
                    if key.lower() not in ('authorization', 'cookie',
                                           'proxy-authorization')
                }
            target = next_url
        else:
            raise ValueError('Too many redirects')
    return {
        'status': response.status_code,
        'url': response.url,
        'headers': {
            'content-type':
            response.headers.get('content-type', 'application/octet-stream')
        },
        'body': base64.b64encode(response.content).decode()
    }


@contextmanager
def transport(task=None):
    from task.toolathlon import root
    root()
    original = importlib.import_module('utils.aux_tools.web_search')
    old_key = original.SERPER_API_KEY
    original.SERPER_API_KEY = os.environ.get('SERPER_API_KEY', '')
    # Upstream includes request headers in exception reprs on API failures.
    secret_filter = SecretFilter()
    original.logger.addFilter(secret_filter)
    records = []
    loop = asyncio.new_event_loop()
    runner = threading.Thread(target=loop.run_forever, daemon=True)
    runner.start()

    def allowed_url(url):
        parsed = urlsplit(url)
        if (task == 'meeting-assign' and parsed.scheme == 'http'
                and parsed.hostname in ('localhost', '127.0.0.1')
                and parsed.port == 30137):
            return
        public_url(url)

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond(None)

        def do_POST(self):
            self.respond(
                json.loads(self.rfile.read(int(
                    self.headers['Content-Length']))))

        def respond(self, body):
            try:
                if self.path == '/tools' and body is None:
                    tool = original.tool_web_search
                    value = {
                        'tools': [{
                            'name': tool.name.removeprefix('local-'),
                            'description': tool.description,
                            'inputSchema': tool.params_json_schema
                        }]
                    }
                elif self.path == '/call':
                    if body['name'] != 'web_search':
                        raise ValueError('Unknown search command')
                    if not original.SERPER_API_KEY:
                        raise RuntimeError('SERPER_API_KEY is required')
                    arguments = body.get('arguments', {})
                    # A search is live on both arms each time it is made.
                    future = asyncio.run_coroutine_threadsafe(
                        original.on_web_search_tool_invoke(
                            None, json.dumps(arguments)), loop)
                    result = redact(future.result())
                    records.append({
                        'kind':
                        'search',
                        'source':
                        'live',
                        'arguments':
                        arguments,
                        'fetched_at':
                        now(),
                        'response_sha256':
                        hashlib.sha256(encode(result)).hexdigest()
                    })
                    value = {'content': [{'type': 'text', 'text': result}]}
                elif self.path == '/http':
                    url = body['url']
                    allowed_url(url)
                    # A page is live on both arms each time it is read.
                    value = read(url, body.get('headers', {}), allowed_url)
                    records.append({
                        'kind':
                        'http',
                        'source':
                        'live',
                        'url':
                        url,
                        'fetched_at':
                        now(),
                        'response_sha256':
                        hashlib.sha256(encode(value)).hexdigest()
                    })
                else:
                    self.send_error(404)
                    return
                status = 200
            except Exception as error:
                status, value = 500, {'error': str(error)}
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    from server.execution import background
    try:
        with background(Handler) as url:
            yield url, records
    finally:
        loop.call_soon_threadsafe(loop.stop)
        runner.join()
        loop.close()
        original.logger.removeFilter(secret_filter)
        original.SERPER_API_KEY = old_key


async def search_tool(context, params):
    """Keep the original local tool schema and return its original text."""
    async with aiohttp.ClientSession() as session:
        async with session.post(os.environ['SEARCH_CLI_URL'] + '/call',
                                json={
                                    'name': 'web_search',
                                    'arguments': json.loads(params)
                                }) as response:
            response.raise_for_status()
            result = await response.json()
            return result['content'][0]['text']


@contextmanager
def serve(task, workdir):
    global CURRENT
    from server.execution import launch
    from server.seed.browser import serve as browser
    from server.seed.papers import TASKS as paper_tasks
    from server.seed.papers import serve as papers
    from task.toolathlon import needed_local_tools, needed_mcp_servers
    if 'web_search' in needed_local_tools(
            task) and not os.environ.get('SERPER_API_KEY'):
        raise RuntimeError('SERPER_API_KEY is required for ' + task)
    previous = CURRENT
    (REPO / 'state/research').mkdir(parents=True, exist_ok=True)
    saved = {
        key: os.environ.get(key)
        for key in ('SEARCH_CLI_URL', 'WEB_API_URL', 'FETCH_CLI_URL')
    }
    servers = needed_mcp_servers(task)
    with ExitStack() as stack:
        stack.callback(restore_environment, saved)
        url, records = stack.enter_context(transport(task))
        os.environ.update(SEARCH_CLI_URL=url, WEB_API_URL=url)
        extra = None
        if task in FINAL_TASKS:
            from server.seed.final_batch import serve as final_services
            extra = stack.enter_context(final_services(task, workdir))
        sheets = None
        if 'google_sheet' in servers:
            from server.seed.research_sheets import serve as sheet_service
            sheets = stack.enter_context(sheet_service(task, workdir))
        if task in paper_tasks:
            stack.enter_context(papers(task, workdir))
        if 'playwright_with_chunk' in servers:
            stack.enter_context(browser(task, workdir))
            if task in FINAL_TASKS:
                from server.seed.final_batch import browser_ready
                browser_ready(task)
        if 'fetch' in servers:
            scratch = Path(
                stack.enter_context(
                    tempfile.TemporaryDirectory(prefix='fetch-',
                                                dir=REPO / 'state/research')))
            endpoint = scratch / 'endpoint'
            params = launch(
                {
                    'command': 'node',
                    'args':
                    [str(REPO / 'server/clients/fetch.mjs'),
                     str(endpoint)],
                    'env': {
                        **os.environ
                    },
                },
                workdir,
                readable=[
                    REPO / 'vendor/fetch-mcp', REPO / 'redirect/research'
                ],
                writable=[scratch])
            log = stack.enter_context((scratch / 'worker.log').open('w'))
            process = subprocess.Popen([params['command'], *params['args']],
                                       cwd=workdir,
                                       env=params['env'],
                                       stdout=log,
                                       stderr=log)
            stack.callback(close, process)
            for _ in range(120):
                if endpoint.is_file():
                    os.environ['FETCH_CLI_URL'] = endpoint.read_text()
                    break
                if process.poll() is not None:
                    raise RuntimeError((scratch / 'worker.log').read_text())
                time.sleep(.1)
            else:
                raise TimeoutError('Original fetch CLI did not start')
        CURRENT = {
            'task': task,
            'requests': records,
            'search': 'original Serper tool, live on both arms',
            'fetch': 'original handlers, live on both arms'
        }
        if extra is not None:
            CURRENT['services'] = {
                k: v
                for k, v in extra.items() if k != 'directory'
            }
        if sheets is not None:
            CURRENT['sheets'] = sheets
        try:
            yield CURRENT
        finally:
            CURRENT = previous
