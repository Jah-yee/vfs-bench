import hashlib
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server.seed import papers  # noqa: E402

PAPER = 'https://arxiv.org/pdf/1234.56789'
SEARCH = ('https://export.arxiv.org/api/query?search_query=Alita&id_list=&'
          'sortBy=relevance&sortOrder=descending&start=0&max_results=100')


def read(base, url):
    with urllib.request.urlopen(base + '/fetch?url=' + quote(url, safe=''),
                                timeout=10) as response:
        return response.read()


class PapersTransport(unittest.TestCase):

    def test_every_request_is_live_each_time_and_off_host_is_refused(self):
        fetched = []

        def get(url, headers=None, timeout=None):
            fetched.append(url)
            return SimpleNamespace(content=b'<feed/>',
                                   url=url,
                                   status_code=200,
                                   headers={'Content-Type': 'text/xml'})

        with patch.object(papers.requests, 'get', get), \
                papers.transport('t') as (base, records):
            self.assertEqual(read(base, PAPER), b'<feed/>')
            self.assertEqual(read(base, SEARCH), b'<feed/>')
            self.assertEqual(read(base, SEARCH), b'<feed/>')
            with self.assertRaises(urllib.error.HTTPError) as refused:
                read(base, 'https://example.org/paper.pdf')
            self.assertEqual(refused.exception.code, 502)
        # The same search asked for twice is fetched twice: nothing is kept.
        self.assertEqual(fetched, [PAPER, SEARCH, SEARCH])
        self.assertEqual([r['source'] for r in records], ['live'] * 3)
        self.assertTrue(all(r['fetched_at'] for r in records))
        self.assertEqual(records[1]['sha256'],
                         hashlib.sha256(b'<feed/>').hexdigest())


if __name__ == '__main__':
    unittest.main()
