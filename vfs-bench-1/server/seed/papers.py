import hashlib
import json
import os
import subprocess
import tempfile
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests

from server.seed.business import restore_environment

REPO = Path(__file__).resolve().parents[2]
HOSTS = ('arxiv.org', 'export.arxiv.org', 'scholar.google.com')
TASKS = {
    'vlm-history-completer': ['arxiv_local'],
    'latex-prompt-box': ['arxiv-latex'],
    'find-alita-paper': ['arxiv_local', 'scholarly'],
    'academic-pdf-report': ['arxiv_local'],
    'add-bibtex': ['scholarly'],
    'logical-datasets-collection': ['scholarly', 'arxiv_local'],
    'profile-update-online': ['scholarly', 'arxiv_local'],
    'llm-training-dataset': ['scholarly']
}
VENDORS = {
    'arxiv-latex': 'arxiv-latex-mcp',
    'arxiv_local': 'arxiv-local-mcp',
    'scholarly': 'scholarly-mcp'
}
CURRENT = None


def active():
    return CURRENT


ENDPOINTS = {
    'arxiv-latex': 'ARXIV_LATEX_CLI_URL',
    'arxiv_local': 'ARXIV_CLI_URL',
    'scholarly': 'SCHOLARLY_CLI_URL'
}


def parameters(kind, workdir):
    from server.mcp.setup_papers_forms import source_root
    source = source_root(VENDORS[kind])
    entry = {
        'arxiv-latex': ['arxiv-latex-mcp.py'],
        'arxiv_local': [
            'original_wrapper.py', '--storage-path',
            str(Path(workdir) / 'arxiv_local_storage')
        ],
        'scholarly': ['-c', 'import mcp_scholarly; mcp_scholarly.main()']
    }[kind]
    if not entry[0].startswith('-'):
        entry[0] = str(source / entry[0])
    return {
        'command': str(source / '.venv/bin/python'),
        'args': entry,
        'cwd': workdir,
        'env': {
            **os.environ, 'PYTHONPATH': str(REPO / 'redirect/papers'),
            'XDG_CACHE_HOME': os.environ['PAPER_CACHE_DIR'],
            'PAPER_API_URL': os.environ['PAPER_API_URL']
        },
    }


def live(url, headers):
    """One live read, recorded but never kept."""
    response = requests.get(url, headers=headers, timeout=90)
    data = response.content
    return {
        'url':
        url,
        'final_url':
        response.url,
        'fetched_at':
        datetime.now(timezone.utc).isoformat(),
        'status':
        response.status_code,
        'content_type':
        response.headers.get('Content-Type', 'application/octet-stream'),
        'sha256':
        hashlib.sha256(data).hexdigest()
    }, data


@contextmanager
def transport(task):
    """Reach arXiv and Scholar live on both arms, recording every request.

    Nothing a run fetches is written anywhere: every request reaches the
    service each time it is made, on either arm, and the run's record
    lists each with its time and response hash.
    """
    records = []

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def do_GET(self):
            try:
                url = parse_qs(urlsplit(self.path).query)['url'][0]
                parsed = urlsplit(url)
                if parsed.scheme not in (
                        'http', 'https'
                ) or parsed.hostname not in HOSTS or parsed.username or (
                        parsed.port):
                    raise ValueError('Unsupported paper HTTP source')
                record, data = live(
                    url, {
                        key: self.headers[key]
                        for key in ('User-Agent', 'Accept', 'Accept-Language')
                        if key in self.headers
                    })
                records.append({'source': 'live', **record})
                self.send_response(record['status'])
                self.send_header('Content-Type', record['content_type'])
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as error:
                self.send_error(502, str(error))

    from server.execution import background
    with background(Handler) as url:
        yield url, records


def close(process, timeout: float = 10):
    """Stop a foreign process, escalating to SIGKILL if it does not go.

    Args:
        process (subprocess.Popen): the process to stop.
        timeout (float): seconds to wait for a clean exit before killing.
    """
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@contextmanager
def serve(task, workdir):
    global CURRENT
    from server.execution import launch
    previous_record = CURRENT
    keys = [
        'PAPER_API_URL', 'PAPER_SOURCE_RECORD', 'PAPER_CACHE_DIR',
        *ENDPOINTS.values()
    ]
    previous = {key: os.environ.get(key) for key in keys}
    with ExitStack() as stack:
        stack.callback(restore_environment, previous)
        url, http_records = stack.enter_context(transport(task))
        os.environ['PAPER_API_URL'] = url
        if 'arxiv_local' in TASKS[task]:
            Path(workdir, 'arxiv_local_storage').mkdir(exist_ok=True)
        (REPO / 'state/papers').mkdir(parents=True, exist_ok=True)
        scratch = Path(
            stack.enter_context(
                tempfile.TemporaryDirectory(prefix='worker-',
                                            dir=REPO / 'state/papers')))
        cache = scratch / 'cache'
        cache.mkdir()
        os.environ['PAPER_CACHE_DIR'] = str(cache)
        for kind in TASKS[task]:
            params = parameters(kind, workdir)
            source = REPO / 'vendor' / VENDORS[kind]
            if kind != 'arxiv_local':
                source /= 'src'
            endpoint = scratch / (kind + '.endpoint')
            endpoint.unlink(missing_ok=True)
            params['env']['PAPER_CLI_ENDPOINT'] = str(endpoint)
            args = [
                params['command'],
                str(REPO / 'server/clients/papers.py'), kind,
                str(source)
            ]
            if kind == 'arxiv_local':
                args += params['args'][1:]
            # A separate interpreter is required by the foreign server's lock.
            params['command'], params['args'] = args[0], args[1:]
            confined = launch(params,
                              workdir,
                              readable=[source],
                              writable=[scratch])
            argv = [confined['command'], *confined['args']]
            log = stack.enter_context((scratch / (kind + '.log')).open('w'))
            process = subprocess.Popen(argv,
                                       cwd=workdir,
                                       env=confined['env'],
                                       stdout=log,
                                       stderr=log)
            stack.callback(close, process)
            for attempt in range(120):
                ready = endpoint.read_text() if endpoint.is_file() else ''
                if ready.startswith('http://127.0.0.1:'):
                    os.environ[ENDPOINTS[kind]] = ready
                    break
                if process.poll() is not None:
                    raise RuntimeError('Original paper CLI failed: ' +
                                       (scratch / (kind + '.log')).read_text())
                time.sleep(.25)
            else:
                raise TimeoutError('Original paper CLI did not start')
        record = {
            'task': task,
            'network': 'live on both arms, nothing kept',
            'requests': http_records
        }
        CURRENT = record
        record_path = REPO / 'state/papers' / (Path(workdir).name + '.json')
        os.environ['PAPER_SOURCE_RECORD'] = str(record_path)
        record_path.write_text(json.dumps(record, indent=2) + '\n')
        try:
            yield record
        finally:
            CURRENT = previous_record
            record_path.write_text(json.dumps(record, indent=2) + '\n')
