import base64
import json
import os
import sys
import types
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server.seed import research  # noqa: E402

PAGE = 'https://example.org/programme.json'


def post(base, path, body):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def fake_search_module():
    module = types.ModuleType('web_search')
    module.SERPER_API_KEY = ''
    module.logger = __import__('logging').getLogger('fake-web-search')
    module.tool_web_search = types.SimpleNamespace(name='local-web_search',
                                                   description='d',
                                                   params_json_schema={})
    module.calls = []

    async def invoke(_, arguments):
        module.calls.append(json.loads(arguments))
        return 'live result ' + str(len(module.calls))

    module.on_web_search_tool_invoke = invoke
    module.__file__ = __file__
    return module


class WebTransport(unittest.TestCase):

    def test_every_page_and_search_is_live_each_time(self):
        module = fake_search_module()
        reads = []

        def read(url, headers, allowed=None):
            reads.append(url)
            return {
                'status': 200,
                'url': url,
                'headers': {
                    'content-type': 'text/plain'
                },
                'body': base64.b64encode(b'live page').decode()
            }

        with patch.object(research, 'read', read), \
                patch.object(research.importlib, 'import_module',
                             lambda name: module), \
                patch.dict(os.environ, {'SERPER_API_KEY': 'k'}):
            with research.transport('t') as (base, records):
                for _ in range(2):
                    page = post(base, '/http', {'url': PAGE, 'headers': {}})
                    self.assertEqual(base64.b64decode(page['body']),
                                     b'live page')
                for _ in range(2):
                    answer = post(base, '/call', {
                        'name': 'web_search',
                        'arguments': {
                            'query': 'x'
                        }
                    })
                    self.assertTrue(
                        answer['content'][0]['text'].startswith('live result'))
            # The same page asked for twice is read twice: nothing is kept.
            self.assertEqual(reads, [PAGE, PAGE])
            self.assertEqual(len(module.calls), 2)
            self.assertEqual([(r['kind'], r['source']) for r in records],
                             [('http', 'live'), ('http', 'live'),
                              ('search', 'live'), ('search', 'live')])
            self.assertTrue(all(r['fetched_at'] for r in records))
            self.assertEqual(records[0]['response_sha256'],
                             records[1]['response_sha256'])


if __name__ == '__main__':
    unittest.main()
