"""Exercise the real Sheets wrapper across out-of-band SQLite restores."""
import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server.clients import gws  # noqa: E402
from server.fakes import stack as fixture_stack  # noqa: E402

# These processes run inside a disposable Linux container, using the same
# SQLite backup API as business_sheets.database. No captured task data is used.
SNAPSHOT = """
import pathlib, sqlite3, sys
live_path = pathlib.Path('/tmp/toolathlon-gws-database').read_text()
with (
    sqlite3.connect(live_path) as live,
    sqlite3.connect('/tmp/snapshot.db') as snapshot,
):
    if sys.argv[1] == 'capture':
        live.backup(snapshot)
    else:
        snapshot.backup(live)
"""
STORED_NAMES = """
import json, pathlib, sqlite3
live_path = pathlib.Path('/tmp/toolathlon-gws-database').read_text()
with sqlite3.connect(live_path) as db:
    print(json.dumps(dict(db.execute('SELECT id, name FROM DriveFile'))))
"""


class SheetsRestore(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Rebuild from this checkout; an old healthy image is not evidence
        # about the currently pinned Mirage implementation. Missing Docker
        # fails the test instead of silently skipping this required check.
        fixture_stack.compose('build', 'api', check=True, timeout=240)

    def docker(self, *args):
        return subprocess.check_output(['docker', *args],
                                       text=True,
                                       stderr=subprocess.STDOUT,
                                       timeout=60).strip()

    def setUp(self):
        # Preserve the production wrapper's relative imports, while using
        # the image's Linux dependencies and generated Prisma client. The
        # image `setUpClass` just built, which is the tag compose.yml names:
        # a stack of its own builds under its own FIXTURES_IMAGE.
        self.container = self.docker(
            'run', '--detach', '--rm', '--init', '--publish',
            '127.0.0.1::19999', '--env', 'MIRAGE_BIND_HOST=0.0.0.0',
            '--volume', f'{REPO}:/source:ro', '--entrypoint', 'sh',
            os.environ.get('FIXTURES_IMAGE', 'toolathlon-fixtures:latest'),
            '-c', 'mkdir -p /opt/fixture-api/server/fakes '
            '/opt/fixture-api/submodule/mirage && '
            'ln -s /opt/toolathlon/integ '
            '/opt/fixture-api/submodule/mirage/integ && '
            'cp /source/server/fakes/gws_api.mjs '
            '/opt/fixture-api/server/fakes/gws_api.mjs && '
            'exec node --import '
            '/opt/toolathlon/integ/node_modules/tsx/dist/loader.mjs '
            '/opt/fixture-api/server/fakes/gws_api.mjs --port 19999 '
            '--fixture-root /source/submodule/mirage/integ/fixtures')
        self.addCleanup(self.docker, 'rm', '--force', self.container)
        address = self.docker('port', self.container, '19999/tcp')
        self.base = 'http://' + address
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                self.api('GET', '/_kit/health')
                return
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(0.1)
        self.fail('Sheets wrapper failed to start:\n' +
                  self.docker('logs', self.container))

    def api(self, method, path, body=None):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {gws.TOKEN}'
            })
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def names(self):
        return {
            row['id']: row['name']
            for row in self.api('GET', '/drive/v3/files')['files']
        }

    def snapshot(self, operation):
        self.docker('exec', self.container, 'python3', '-c', SNAPSHOT,
                    operation)

    def check_restore(self, read_first):
        created = self.api(
            'POST', '/drive/v3/files', {
                'name': 'restored-sheet',
                'mimeType': 'application/vnd.google-apps.spreadsheet'
            })
        file_id = created['id']
        self.snapshot('capture')
        self.api('PATCH', '/drive/v3/files/' + file_id,
                 {'name': 'stale-cached-sheet'})
        self.assertEqual(self.names()[file_id], 'stale-cached-sheet')

        # This changes the authoritative rows without using an API/reset
        # route, leaving Mirage's already-warmed request cache stale.
        self.snapshot('restore')
        if read_first:
            self.assertEqual(self.names()[file_id], 'restored-sheet')
        added = self.api(
            'POST', '/drive/v3/files', {
                'name': 'after-restore',
                'mimeType': 'application/vnd.google-apps.spreadsheet'
            })
        self.assertNotEqual(added['id'], file_id)
        expected = {file_id: 'restored-sheet', added['id']: 'after-restore'}
        self.assertEqual(self.names(), expected)
        stored = self.docker('exec', self.container, 'python3', '-c',
                             STORED_NAMES)
        self.assertEqual(json.loads(stored), expected)

    def test_read_then_write_after_restore(self):
        self.check_restore(read_first=True)

    def test_first_write_after_restore(self):
        self.check_restore(read_first=False)


if __name__ == '__main__':
    unittest.main()
