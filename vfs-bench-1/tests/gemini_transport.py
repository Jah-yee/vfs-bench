import asyncio
import json
import sys
import unittest
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from agent.gemini import NativeGemini  # noqa: E402


class Sent(httpx.AsyncBaseTransport):
    """Keep what NativeGemini hands on, and answer an empty reply."""

    def __init__(self):
        self.requests = []

    async def handle_async_request(self, request):
        self.requests.append(request)
        return httpx.Response(200, json={'candidates': []})


class Transport(unittest.TestCase):

    def test_the_request_keeps_the_clients_timeout(self):
        # A rebuilt request with no timeout can wait an hour on one reply.
        native = NativeGemini()
        native.inner = Sent()

        async def post():
            async with httpx.AsyncClient(transport=native,
                                         timeout=httpx.Timeout(
                                             600, connect=5)) as http:
                return await http.post('http://gateway/v1beta/models/m',
                                       json={'system_instruction': {}})

        reply = asyncio.run(post())
        self.assertEqual(reply.status_code, 200)
        [sent] = native.inner.requests
        self.assertEqual(sent.extensions['timeout'], {
            'connect': 5,
            'read': 600,
            'write': 600,
            'pool': 600
        })
        self.assertEqual(json.loads(sent.content), {'systemInstruction': {}})


if __name__ == '__main__':
    unittest.main()
