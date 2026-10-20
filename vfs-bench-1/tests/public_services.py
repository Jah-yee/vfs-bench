import json
import os
import sys
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server.seed import public_services  # noqa: E402

URL = 'https://youtube.googleapis.com/youtube/v3/videos?part=snippet&id=zzz'


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as response:
        return response.status, response.read()


class PublicServices(unittest.TestCase):

    def test_every_answer_is_live_and_the_key_never_reaches_the_record(self):
        lives = []

        def request(method, url, headers=None, data=None, timeout=None):
            lives.append(url)
            return SimpleNamespace(status_code=200,
                                   ok=True,
                                   content=b'live',
                                   headers={'Content-Type': 'text/plain'},
                                   raw=SimpleNamespace(headers=SimpleNamespace(
                                       getlist=lambda name: [])))

        with patch.object(public_services.requests, 'request', request), \
                patch.dict(os.environ, {'YOUTUBE_API_KEY': 'SECRET'}):
            with public_services.serve() as (base, records):
                for _ in range(2):
                    status, body = get(
                        base, '/youtube/v3/videos?part=snippet&id=zzz'
                        '&key=SECRET')
                    self.assertEqual((status, body), (200, b'live'))
            # The same request asked for twice is fetched twice.
            self.assertEqual(lives, [URL + '&key=SECRET'] * 2)
            self.assertEqual([r['source'] for r in records], ['live', 'live'])
            self.assertEqual(records[0]['request']['url'], URL)
            self.assertTrue(all(r['fetched_at'] for r in records))
            self.assertEqual(records[0]['response_sha256'],
                             records[1]['response_sha256'])
            # The key never reaches the record.
            self.assertNotIn('SECRET', json.dumps(records))


if __name__ == '__main__':
    unittest.main()
