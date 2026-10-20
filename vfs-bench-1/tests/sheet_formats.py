"""The audit's format overlay must preserve values and field-mask semantics."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.fakes import sheet_formats  # noqa: E402
from server.fakes.sheet_formats import Formats, formatted  # noqa: E402

SHEETS = [{
    'properties': {
        'sheetId': n,
        'gridProperties': {
            'rowCount': 5,
            'columnCount': 3
        }
    }
} for n in (0, 1)]


class SheetFormats(unittest.TestCase):

    def test_gdp_number_formats(self):
        percent = {'numberFormat': {'type': 'PERCENT', 'pattern': '0.00%'}}
        number = {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0.00'}}
        self.assertEqual(formatted(0.994365515905266, percent), '99.44%')
        self.assertEqual(formatted(27613326.339868877, number),
                         '27,613,326.34')

    def test_other_patterns_keep_the_fakes_rendering(self):
        # gdp-cr5-analysis wrote CR5 as `0.00"%"` and inter-final ages as
        # `0.0`; Google shows 87.60% and 27.0, and so does the fake.
        quoted = {'numberFormat': {'type': 'NUMBER', 'pattern': '0.00"%"'}}
        tenth = {'numberFormat': {'type': 'NUMBER', 'pattern': '0.0'}}
        self.assertIsNone(formatted(87.6, quoted))
        self.assertIsNone(formatted(27, tenth))
        self.assertEqual(formatted(27, {}), '27')
        state = Formats()
        for row, fmt in enumerate((quoted, tenth)):
            state.cells[0, row, 4] = fmt
        sheet = {'properties': {'sheetId': 0, 'title': 'Sheet1'}}
        grid = dict(sheet,
                    data=[{
                        'rowData': [{
                            'values':
                            [{}
                             for _ in range(4)] + [{
                                 'effectiveValue': {
                                     'numberValue': value
                                 },
                                 'formattedValue': text
                             }]
                        } for value, text in ((87.6, '87.60%'), (27, '27.0'))]
                    }])
        data = {'range': 'Sheet1!E1:E2', 'values': [['87.60%'], ['27.0']]}
        sheet_formats.render_values(data, state, {'sheets': [grid]})
        self.assertEqual(data['values'], [['87.60%'], ['27.0']])
        state.overlay({'sheets': [grid]})
        self.assertEqual([
            row['values'][4]['formattedValue']
            for row in grid['data'][0]['rowData']
        ], ['87.60%', '27.0'])

    def test_range_read_places_formats_from_its_start(self):
        # inter-final-performance-analysis read B17:C18 after formatting it;
        # the header's format belongs to row 1, not to the block's first row.
        tenth = {'numberFormat': {'type': 'NUMBER', 'pattern': '0.0'}}
        header = {'textFormat': {'fontFamily': 'Arial', 'bold': False}}
        state = Formats()
        state.cells[0, 0, 0] = header
        for row in (16, 17):
            for column in (1, 2):
                state.cells[0, row, column] = tenth
        block = {'startRow': 16, 'startColumn': 1, 'rowData': []}
        for pair in (((28.9, '28.9'), (27.7, '27.7')), ((29.7, '29.7'),
                                                        (27, '27.0'))):
            block['rowData'].append({
                'values': [{
                    'effectiveValue': {
                        'numberValue': value
                    },
                    'formattedValue': text
                } for value, text in pair]
            })
        document = {
            'sheets': [{
                'properties': {
                    'sheetId': 0
                },
                'data': [block]
            }]
        }
        state.overlay(document, ranged=True)
        rows = document['sheets'][0]['data'][0]['rowData']
        self.assertEqual(len(rows), 2)
        self.assertTrue(
            all(cell['userEnteredFormat'] == tenth for row in rows
                for cell in row['values']))
        self.assertEqual(rows[1]['values'][1]['formattedValue'], '27.0')

    def test_mask_preserves_other_formats_and_value_requests(self):
        state = Formats()
        initial = {
            'updateCells': {
                'start': {
                    'sheetId': 0
                },
                'rows': [{
                    'values': [{
                        'userEnteredFormat': {
                            'textFormat': {
                                'bold': True,
                                'italic': True
                            },
                            'horizontalAlignment': 'CENTER'
                        }
                    }]
                }],
                'fields':
                'userEnteredFormat'
            }
        }
        state.translate([initial], SHEETS)
        update = {
            'updateCells': {
                'start': {
                    'sheetId': 0
                },
                'rows': [{
                    'values': [{
                        'userEnteredValue': {
                            'stringValue': 'new'
                        },
                        'userEnteredFormat': {
                            'textFormat': {
                                'bold': False
                            }
                        }
                    }]
                }],
                'fields':
                'userEnteredValue,userEnteredFormat.textFormat.bold'
            }
        }
        self.assertEqual(state.translate([update], SHEETS), [update])
        value = {'userEnteredValue': {'stringValue': 'new'}}
        doc = {
            'sheets': [{
                'properties': {
                    'sheetId': 0
                },
                'data': [{
                    'rowData': [{
                        'values': [value]
                    }]
                }]
            }]
        }
        state.overlay(doc)
        self.assertEqual(value['userEnteredValue'], {'stringValue': 'new'})
        self.assertEqual(
            value['userEnteredFormat'], {
                'textFormat': {
                    'bold': False,
                    'italic': True
                },
                'horizontalAlignment': 'CENTER'
            })
        update['updateCells']['fields'] = 'userEnteredFormat.textFormat.italic'
        state.translate([update], SHEETS)
        self.assertNotIn('italic', state.cells[0, 0, 0]['textFormat'])

    def test_repeat_and_cross_sheet_format_copy(self):
        state = Formats()
        area = {'sheetId': 0, 'endRowIndex': 1, 'endColumnIndex': 3}
        repeat = {
            'repeatCell': {
                'range': area,
                'fields': 'userEnteredFormat',
                'cell': {
                    'userEnteredFormat': {
                        'textFormat': {
                            'bold': True
                        }
                    }
                }
            }
        }
        translated = state.translate([repeat], SHEETS)
        self.assertEqual(translated[0]['updateCells']['fields'],
                         'userEnteredFormat')
        target = {
            'sheetId': 1,
            'startRowIndex': 1,
            'endRowIndex': 4,
            'endColumnIndex': 3
        }
        state.translate([{
            'copyPaste': {
                'source': area,
                'destination': target,
                'pasteType': 'PASTE_FORMAT'
            }
        }], SHEETS)
        self.assertEqual(sum(k[0] == 1 for k in state.cells), 9)
        self.assertTrue(
            all(v['textFormat']['bold'] for v in state.cells.values()))
        snapshot = copy.deepcopy(state.cells)
        with self.assertRaisesRegex(ValueError, 'Invalid sheetId'):
            state.translate([{
                'repeatCell': {
                    'range': {
                        'sheetId': 99
                    },
                    'fields': 'userEnteredFormat',
                    'cell': {}
                }
            }], SHEETS)
        self.assertEqual(state.cells, snapshot)

    def test_range_clear_and_format_only_cells_survive_reads(self):
        state = Formats()
        state.translate([{
            'updateCells': {
                'start': {
                    'sheetId': 0,
                    'rowIndex': 2
                },
                'fields':
                'userEnteredFormat',
                'rows': [{
                    'values': [{
                        'userEnteredFormat': {
                            'textFormat': {
                                'bold': True
                            }
                        }
                    }]
                }]
            }
        }], SHEETS)
        document = {'sheets': [{'properties': {'sheetId': 0}, 'data': [{}]}]}
        state.overlay(document)
        self.assertEqual(len(document['sheets'][0]['data'][0]['rowData']), 3)
        state.translate([{
            'updateCells': {
                'range': {
                    'sheetId': 0,
                    'startRowIndex': 2,
                    'endRowIndex': 3,
                    'endColumnIndex': 1
                },
                'fields': 'userEnteredFormat',
                'rows': []
            }
        }], SHEETS)
        self.assertEqual(state.cells[0, 2, 0], {})

    def test_read_mask_drops_overlaid_formats(self):
        percent = {'numberFormat': {'type': 'PERCENT', 'pattern': '0.00%'}}
        state = Formats()
        state.translate([{
            'updateCells': {
                'start': {
                    'sheetId': 0
                },
                'fields': 'userEnteredFormat',
                'rows': [{
                    'values': [{
                        'userEnteredFormat': percent
                    }]
                }]
            }
        }], SHEETS)
        cell = {'effectiveValue': {'numberValue': 0.5}}
        document = {
            'sheets': [{
                'properties': {
                    'sheetId': 0,
                    'title': 'Sheet1'
                },
                'data': [{
                    'rowData': [{
                        'values': [cell]
                    }]
                }]
            }]
        }
        state.overlay(document)
        self.assertEqual(cell['effectiveFormat'], percent)
        mask = sheet_formats.read_mask(
            'sheets(properties/title,data(rowData(values('
            'formattedValue,effectiveValue))))')
        self.assertEqual(
            sheet_formats.masked(document, mask), {
                'sheets': [{
                    'properties': {
                        'title': 'Sheet1'
                    },
                    'data': [{
                        'rowData': [{
                            'values': [{
                                'effectiveValue': {
                                    'numberValue': 0.5
                                },
                                'formattedValue': '50.00%'
                            }]
                        }]
                    }]
                }]
            })
        self.assertEqual(
            sheet_formats.masked(document, sheet_formats.read_mask('*')),
            document)

    def test_mask_without_sheet_ids_reads_unmasked(self):
        read = '/v4/spreadsheets/s1?includeGridData=true&ranges=Week3'
        self.assertEqual(
            sheet_formats.unmasked(
                read +
                '&fields=sheets(data(rowData(values(formattedValue))))'), read)
        self.assertEqual(
            sheet_formats.unmasked(
                read + '&fields=sheets(properties/title,data(rowData))'), read)
        for mask in (
                'sheets(properties,data(rowData(values(formattedValue))))',
                'sheets(properties(title,sheetId))', 'properties.title',
                'sheets/*', '*'):
            self.assertEqual(sheet_formats.unmasked(f'{read}&fields={mask}'),
                             f'{read}&fields={mask}')


if __name__ == '__main__':
    unittest.main()
