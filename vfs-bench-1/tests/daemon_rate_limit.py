import asyncio
import sys
import time
import unittest
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'agent'))
from agent.workspace import Patient, retry_after  # noqa: E402


def limited(refusals: int, seen: list):
    """A daemon that turns the first `refusals` requests away with 429."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        if len(seen) <= refusals:
            return httpx.Response(429,
                                  headers={'Retry-After': '0'},
                                  json={'detail': 'Too Many Requests'})
        return httpx.Response(200, json={'job_id': 'j1'})

    return handler


class RateLimit(unittest.TestCase):
    """A request the daemon refuses for its rate goes again."""

    def test_the_sync_client_resends_until_it_is_let_through(self):
        seen = []
        with httpx.Client(base_url='http://daemon',
                          transport=Patient(
                              httpx.MockTransport(limited(2, seen)))) as http:
            reply = http.post('/v1/workspaces/w/shell', json={'command': 'ls'})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json(), {'job_id': 'j1'})
        self.assertEqual(seen, [b'{"command":"ls"}'] * 3)

    def test_the_async_client_resends_a_multipart_body_whole(self):
        seen = []

        async def post():
            async with httpx.AsyncClient(base_url='http://daemon',
                                         transport=Patient(
                                             httpx.MockTransport(
                                                 limited(3, seen)))) as http:
                return await http.post('/v1/workspaces/w/shell',
                                       files={
                                           'request': ('request.json',
                                                       '{"command":"cat"}',
                                                       'application/json'),
                                           'stdin':
                                           ('stdin.bin', b'bytes',
                                            'application/octet-stream'),
                                       })

        reply = asyncio.run(post())
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(len(seen), 4)
        self.assertEqual(len(set(seen)), 1)
        self.assertIn(b'bytes', seen[0])

    def test_a_daemon_that_keeps_refusing_gets_its_429_to_the_caller(self):
        # Resent only while the client's read timeout lasts, on both paths.
        for retry, attempts in [('1', 1), ('0', None)]:
            with self.subTest(retry_after=retry):
                seen = []

                def refuse(request):
                    seen.append(request)
                    return httpx.Response(429, headers={'Retry-After': retry})

                started = time.monotonic()
                with httpx.Client(transport=Patient(
                        httpx.MockTransport(refuse)),
                                  timeout=0.3) as http:
                    self.assertEqual(
                        http.get('http://daemon/v1/jobs/j').status_code, 429)

                async def get():
                    async with httpx.AsyncClient(transport=Patient(
                            httpx.MockTransport(refuse)),
                                                 timeout=0.3) as http:
                        return await http.get('http://daemon/v1/jobs/j')

                self.assertEqual(asyncio.run(get()).status_code, 429)
                self.assertLess(time.monotonic() - started, 2)
                if attempts:
                    self.assertEqual(len(seen), 2 * attempts)
                else:
                    self.assertGreater(len(seen), 2)

    def test_any_other_status_is_returned_as_it_came(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(503)

        with httpx.Client(
                transport=Patient(httpx.MockTransport(handler))) as http:
            self.assertEqual(
                http.get('http://daemon/v1/jobs/j').status_code, 503)
        self.assertEqual(len(seen), 1)

    def test_the_wait_is_the_daemons_retry_after(self):
        for header, wait in [({
                'Retry-After': '7'
        }, 7.0), ({}, 1.0), ({
                'Retry-After': 'soon'
        }, 1.0), ({
                'Retry-After': '-2'
        }, 0.0)]:
            with self.subTest(header=header):
                self.assertEqual(
                    retry_after(httpx.Response(429, headers=header)), wait)


if __name__ == '__main__':
    unittest.main()
