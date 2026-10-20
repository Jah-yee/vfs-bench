"""Package selection and the built task runtime, without downloading wheels."""
import asyncio
import hashlib
import json
import os
import sys
import tarfile
import tempfile
import unittest
import zipfile
from contextlib import ExitStack, chdir
from pathlib import Path
from unittest.mock import patch

import yaml

from task.toolathlon.script import setup_upstream_python as packages


class BundleLineage(unittest.TestCase):

    def test_dvc_detects_missing_and_corrupt_runtime_assets(self):
        from dvc.repo import Repo

        stage_name = 'toolathlon-python-packages'
        source = yaml.safe_load((packages.REPO_ROOT /
                                 'dvc.yaml').read_text())['stages'][stage_name]
        with tempfile.TemporaryDirectory() as tmp, chdir(tmp):
            root = Path(tmp)
            Repo.init(tmp, no_scm=True).close()
            bundle = root / 'vendor/toolathlon-python'
            bundle.mkdir(parents=True)
            (bundle / 'manifest.json').write_text('{}')
            (bundle / 'pyodide-lock.json').write_text('{}')
            assets = [bundle / 'package.whl', bundle / 'dependency.whl']
            for asset in assets:
                asset.write_bytes(b'original runtime bytes')
            (root / 'dvc.yaml').write_text(
                yaml.safe_dump({
                    'stages': {
                        stage_name: {
                            'cmd': source['cmd'],
                            'outs': source['outs']
                        }
                    }
                }))
            with Repo(tmp) as repo:
                repo.commit(target=stage_name, force=True)

            def status():
                with Repo(tmp) as repo:
                    return repo.status(targets=[stage_name])

            self.assertEqual(status(), {})
            for asset in assets:
                original = asset.read_bytes()
                for change in ('missing', 'corrupt'):
                    with self.subTest(asset=asset.name, change=change):
                        try:
                            if change == 'missing':
                                asset.unlink()
                            else:
                                asset.write_bytes(b'X' + original[1:])
                            self.assertTrue(status())
                        finally:
                            asset.write_bytes(original)
                        self.assertEqual(status(), {})


class PackageLock(unittest.TestCase):

    def test_namespace_imports_come_from_shipped_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / 'example.whl'
            with zipfile.ZipFile(wheel, 'w') as archive:
                for name in ('google/cloud/storage/__init__.py',
                             'google/cloud/storage/internal/__init__.py',
                             'standalone.py', 'regular/__init__.py',
                             'regular/child/__init__.py'):
                    archive.writestr(name, '')
                archive.writestr('example.dist-info/top_level.txt',
                                 'tests\ndocs\n')
            self.assertEqual(packages.imports_of(wheel),
                             ['google.cloud.storage', 'regular', 'standalone'])

    def test_native_dependency_alias_survives_and_stale_lock_fails(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            dest = root / 'wheels'
            dest.mkdir()
            entries = {}
            for name, depends in (('pydantic', ['pydantic_core']),
                                  ('pydantic_core', [])):
                filename = name + '.whl'
                body = b'test wheel bytes'
                (dest / filename).write_bytes(body)
                entries[name] = {
                    'name': name,
                    'version': '1.0',
                    'file_name': filename,
                    'sha256': hashlib.sha256(body).hexdigest(),
                    'depends': depends,
                    'imports': [name],
                }
            (root / 'pyodide-lock.json').write_text(
                json.dumps({
                    'info': {},
                    'packages': entries
                }))
            (root / 'package.json').write_text('{"version": "test"}')
            stack.enter_context(patch.object(packages, 'DEST', dest))
            stack.enter_context(
                patch.object(packages, 'WANTED', ('pydantic', )))
            stack.enter_context(
                patch.object(packages, 'pyodide_dir', return_value=root))
            stack.enter_context(
                patch.object(packages,
                             'installed_upstream',
                             return_value={
                                 'pydantic': '1.0',
                                 'trio': '1.0'
                             }))
            stack.enter_context(
                patch.object(packages,
                             'upstream_lock',
                             return_value={
                                 'pydantic': {
                                     'version': '1.0'
                                 },
                                 'trio': {
                                     'version': '1.0'
                                 }
                             }))
            self.assertEqual(packages.main([]), 0)
            lock = json.loads((dest / 'pyodide-lock.json').read_text())
            self.assertEqual(lock['packages']['pydantic']['depends'],
                             ['pydantic-core'])
            self.assertIn('pydantic-core', lock['packages'])
            self.assertNotIn('trio', lock['packages'])
            self.assertEqual(packages.main(['--check']), 0)
            (dest / 'pyodide-lock.json').write_text('{}')
            self.assertEqual(packages.main(['--check']), 1)

    def test_unsynced_upstream_environment_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            (root / 'pyodide-lock.json').write_text('{"packages": {}}')
            (root / 'package.json').write_text('{"version": "test"}')
            stack.enter_context(patch.object(packages, 'WANTED', ('numpy', )))
            stack.enter_context(
                patch.object(packages, 'pyodide_dir', return_value=root))
            stack.enter_context(
                patch.object(packages,
                             'upstream_lock',
                             return_value={'numpy': {
                                 'version': 'locked'
                             }}))
            stack.enter_context(
                patch.object(packages,
                             'installed_upstream',
                             return_value={'numpy': 'unlocked'}))
            with self.assertRaisesRegex(SystemExit, 'differs from uv.lock'):
                packages.main(['--check'])


@unittest.skipUnless(
    (packages.DEST / 'pyodide-lock.json').is_file()
    and (packages.REPO_ROOT / 'submodule/mirage/typescript/packages/server/'
         'dist/bin/daemon.js').is_file(), 'requires the built Mirage runtime')
class ArrangeWorkspace(unittest.TestCase):

    def test_python_packages_and_workspace_paths(self):
        for path in ('agent', 'task'):
            sys.path.insert(0, str(packages.REPO_ROOT / path))
        from workspace import Workspace

        task = packages.REPO_ROOT / 'task/toolathlon/arrange-workspace/vfs'
        imports = ('import openpyxl, xlsxwriter, PyPDF2, pymupdf, pandas, '
                   'numpy, pyarrow, PIL, lxml, docx, pptx\n')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
                os.environ, {
                    'AGENT_WORKSPACE': tmp,
                    'TOOLATHLON_PYTHON': str(packages.DEST),
                    'PDF_TOOLS_CLI_URL': '',
                    'EXCEL_CLI_URL': '',
                }):
            archive = packages.UPSTREAM / (
                'tasks/finalpool/arrange-workspace/initial_workspace/'
                'initial_workspace.tar.gz')
            with tarfile.open(archive) as source:
                member = next(m for m in source.getmembers()
                              if Path(m.name).name == 'course_schedule.xls')
                (Path(tmp) / 'course_schedule.xls').write_bytes(
                    source.extractfile(member).read())
                for member in source.getmembers():
                    if member.isfile() and Path(
                            member.name).suffix.lower() in {'.jpg', '.png'}:
                        (Path(tmp) / Path(member.name).name).write_bytes(
                            source.extractfile(member).read())
            workspace = Workspace.create(task / 'workspace.yaml')
            try:
                self.assertEqual(
                    workspace.execute('echo "$HOME"; echo ~; pwd'),
                    '/workspace\n' * 3)
                # Test dynamic imports before any static imports load them.
                probe = workspace.execute("""python3 - <<'PY'
for pkg in ['pytesseract', 'easyocr', 'cv2', 'xlrd', 'olefile']:
    try:
        __import__(pkg)
        print(pkg, 'available')
    except ImportError:
        print(pkg, 'NOT available')
PY""")
                self.assertEqual(
                    probe, 'pytesseract available\n'
                    'easyocr NOT available\ncv2 NOT available\n'
                    'xlrd NOT available\nolefile available\n')
                code = imports + '''
import olefile
assert olefile.__version__ == '0.47'
with olefile.OleFileIO('/workspace/course_schedule.xls') as ole:
    assert ole.openstream('Workbook').read()
import os
from pathlib import Path
assert os.environ['HOME'] == '/workspace'
assert os.path.expanduser('~') == '/workspace'
assert str(Path.home()) == '/workspace'
assert str(Path.cwd()) == '/workspace'
(Path.home() / 'home-proof.txt').write_text('python')
print('IMPORTS_AND_HOME_OK')
'''
                output = workspace.execute("python3 - <<'PY'\n" + code +
                                           '\nPY')
                self.assertIn('IMPORTS_AND_HOME_OK', output)
                self.assertEqual((Path(tmp) / 'home-proof.txt').read_text(),
                                 'python')
                # Upstream's image has pytesseract but no tesseract binary,
                # so OCR raises there (TesseractNotFoundError, an OSError);
                # it has no engine here either.
                ocr = workspace.execute("""python3 - <<'PY'
import errno
import pytesseract
import js
from PIL import Image
assert not hasattr(js, 'process') and not hasattr(js, 'fetch')
image = Image.open('/workspace/course_model_weight_1.png')
image.load()
try:
    pytesseract.get_tesseract_version()
except pytesseract.TesseractNotFoundError:
    pass
else:
    raise AssertionError('an OCR engine answered')
try:
    pytesseract.image_to_string(image)
except OSError as error:
    assert error.errno == errno.ENOTSUP, error
    print('NO_OCR')
PY""")
                self.assertEqual(ocr, 'NO_OCR\n')
                workspace.execute("echo shell > ~/tilde-proof.txt")
                self.assertEqual((Path(tmp) / 'tilde-proof.txt').read_text(),
                                 'shell\n')
                asyncio.run(workspace.save_overflow('preserved output'))
                saved = list((Path(tmp) / '.overlong_tool_outputs').glob('*'))
                self.assertEqual(len(saved), 1)
                self.assertEqual(saved[0].read_text(), 'preserved output')
            finally:
                workspace.close()


if __name__ == '__main__':
    unittest.main()
