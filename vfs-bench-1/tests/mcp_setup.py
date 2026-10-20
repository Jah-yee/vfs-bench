"""Setup scripts must load when invoked by path without PYTHONPATH."""
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = ('calendar', 'fetch', 'howtocook', 'huggingface', 'snowflake',
           'google_cloud')


class SetupImports(unittest.TestCase):

    def test_file_entry_points_without_repo_on_path(self):
        # Reproduce Python's script-directory sys.path without spawning a
        # sibling module or running package installers. Drop cached server
        # modules so a previous import cannot conceal a broken entry point.
        paths = [p for p in sys.path if Path(p).resolve() != REPO]
        for name in SCRIPTS:
            script = REPO / 'server/mcp' / f'setup_{name}.py'
            with self.subTest(script=name), patch.dict(sys.modules), \
                    patch.object(sys, 'path', [str(script.parent), *paths]):
                for module in list(sys.modules):
                    if module == 'server' or module.startswith('server.'):
                        del sys.modules[module]
                namespace = runpy.run_path(str(script))
                self.assertTrue(callable(namespace['main']))
                self.assertEqual(namespace['REPO'], REPO)


if __name__ == '__main__':
    unittest.main()
