"""Keep the original commerce Sheets captures usable across Mirage schemas."""
import gzip
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from server.seed.business_sheets import current_snapshot  # noqa: E402


class SheetsSnapshotMigration(unittest.TestCase):

    def test_existing_commerce_captures(self):
        for task in ('update-material-inventory', 'woocommerce-stock-alert'):
            with self.subTest(task=task):
                capture = (REPO / 'task/toolathlon' / task /
                           'shared/fixtures/woocommerce/sheets.db.gz')
                source = gzip.decompress(capture.read_bytes())
                migrated = current_snapshot(source)
                self.assertEqual(current_snapshot(migrated), migrated)
                with tempfile.NamedTemporaryFile(suffix='.db') as old_file, \
                        tempfile.NamedTemporaryFile(suffix='.db') as new_file:
                    old_file.write(source)
                    old_file.flush()
                    new_file.write(migrated)
                    new_file.flush()
                    with sqlite3.connect(old_file.name) as old, \
                            sqlite3.connect(new_file.name) as new:
                        # A capture taken on the current schema already has
                        # these columns, holding the workbook's own formats,
                        # so only a column the migration added must be empty.
                        for table, defaults in (
                            ('SheetTab', {
                                'rowMeta': '{}',
                                'columnMeta': '{}',
                                'bandedRanges': '[]',
                                'basicFilter': None,
                                'conditionalFormats': '[]',
                            }),
                            ('SheetCell', {
                                'props': '{}'
                            }),
                        ):
                            columns = [
                                row[1] for row in old.execute(
                                    f'PRAGMA table_info({table})')
                            ]
                            order = ', '.join(columns)
                            self.assertEqual(
                                old.execute(f'SELECT {order} FROM {table} '
                                            'ORDER BY rowid').fetchall(),
                                new.execute(f'SELECT {order} FROM {table} '
                                            'ORDER BY rowid').fetchall())
                            for column, default in defaults.items():
                                if column in columns:
                                    continue
                                self.assertTrue(
                                    all(row[0] == default
                                        for row in new.execute(
                                            f'SELECT {column} FROM {table}')))
                self.assertEqual(gzip.decompress(capture.read_bytes()), source)


class TemplateRemoval(unittest.TestCase):
    """Upstream's template leaves the model's Drive once it is copied."""

    def test_the_template_is_deleted_by_its_upstream_id(self):
        from unittest.mock import patch

        from server.seed import business_sheets
        with patch.object(business_sheets.gws, 'call') as call:
            business_sheets.remove_source('woocommerce-stock-alert')
        call.assert_called_once_with(
            'DELETE', '/drive/v3/files/'
            '1cMNmXLps78jD-_5bYZlQRitx7mHXagInEHLWW2cBwEY')

    def test_a_run_removes_it_after_serve_and_only_for_a_sheet(self):
        from contextlib import contextmanager
        from unittest.mock import patch

        from server.seed import business, business_sheets
        sys.path.insert(0, str(REPO / 'task'))
        import toolathlon
        order = []

        @contextmanager
        def serve(task, workdir):
            order.append('serve')
            yield {'task': task}

        with patch.object(business, 'serve', serve), patch.object(
                business_sheets, 'remove_source',
                lambda task: order.append('remove ' + task)):
            with toolathlon._services('woocommerce-stock-alert', '/tmp'):
                order.append('run')
            with toolathlon._services('woocommerce-new-product', '/tmp'):
                pass
        self.assertEqual(
            order, ['serve', 'remove woocommerce-stock-alert', 'run', 'serve'])

    def test_a_capture_keeps_the_template_its_restore_checks(self):
        # A capture enters `business.serve` itself, not the run's seam that
        # removes the template, and records the Drive; a restore then
        # checks the copy against the template it recorded.
        from server.seed import business, business_sheets
        from task.toolathlon.script import capture_woocommerce
        self.assertIs(capture_woocommerce.serve, business.serve)
        for task in ('update-material-inventory', 'woocommerce-stock-alert'):
            with self.subTest(task=task):
                source = json.loads((business_sheets.source_folder(task) /
                                     'source.json').read_text())
                capture = (REPO / 'task/toolathlon' / task /
                           'shared/fixtures/woocommerce/sheets.db.gz')
                with tempfile.NamedTemporaryFile(suffix='.db') as file:
                    file.write(gzip.decompress(capture.read_bytes()))
                    file.flush()
                    with sqlite3.connect(file.name) as db:
                        ids = {
                            row[0]
                            for row in db.execute('SELECT id FROM Spreadsheet')
                        }
                self.assertIn(source['sheet_id'], ids)


if __name__ == '__main__':
    unittest.main()
