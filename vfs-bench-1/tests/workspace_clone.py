import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import server.clone  # noqa: E402


class Clone(unittest.TestCase):

    def test_a_clone_is_the_copy(self):
        # Either way the run gets the fixture's bytes, mode and times, and a
        # write to its file never reaches the fixture's.
        ways = {'copy2': None}
        if server.clone.CLONEFILE is not None:
            ways['clonefile'] = server.clone.CLONEFILE
        for way, clonefile in ways.items():
            with self.subTest(way=way), tempfile.TemporaryDirectory(
            ) as scratch, patch.object(server.clone, 'CLONEFILE', clonefile):
                src, dst = Path(scratch, 'fixture'), Path(scratch, 'run')
                src.write_bytes(b'upstream\n')
                src.chmod(0o640)
                os.utime(src, ns=(1_000_000_000, 2_000_000_000))
                self.assertEqual(server.clone.clone(src, dst), dst)
                self.assertEqual(dst.read_bytes(), b'upstream\n')
                self.assertEqual(dst.stat().st_mode, src.stat().st_mode)
                self.assertEqual(dst.stat().st_mtime_ns, 2_000_000_000)
                dst.write_bytes(b'the run wrote this\n')
                self.assertEqual(src.read_bytes(), b'upstream\n')

    @unittest.skipUnless(sys.platform == 'darwin', 'clonefile(2) is macOS')
    def test_macos_takes_the_native_path(self):
        # Where runs are drawn, a lookup that stopped finding clonefile would
        # pass every other test as the copy2 fallback.
        self.assertIsNotNone(server.clone.CLONEFILE)

    def test_an_existing_destination_is_overwritten(self):
        # As copy2 does: clonefile refuses one, and copy2 then writes it.
        with tempfile.TemporaryDirectory() as scratch:
            src, dst = Path(scratch, 'fixture'), Path(scratch, 'run')
            src.write_bytes(b'upstream\n')
            dst.write_bytes(b'stale\n')
            server.clone.clone(src, dst)
            self.assertEqual(dst.read_bytes(), b'upstream\n')


if __name__ == '__main__':
    unittest.main()
