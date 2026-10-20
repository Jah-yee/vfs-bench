---
name: workspace-commands
description: The shell commands, task tools, and python3 interpreter available in this workspace.
---

# Available commands

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip  curl

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## Google Drive and spreadsheet reads

Use `ls` and `find` under `/gd` to list folders and locate spreadsheets.
Read `.gsheet.json` files with `cat`, `jq`, or Python to inspect spreadsheet
IDs, tab names, cell values, formulas, and metadata. Filter or
slice the JSON for ranges, summaries, and matching cells; read multiple
files for queries across spreadsheets. See VFS.md for the JSON structure.

## google-sheet

Use `google-sheet <command> '<JSON arguments>'`. Run
`google-sheet <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `google-sheet get-sheet-data` | `{spreadsheet_id: str, sheet: str, range?: str = null, include_grid_data?: bool = false}` | Get data from a specific sheet in a Google Spreadsheet. Args: spreadsheet_id: The ID of the spreadsheet (found in the URL) sheet: The name of the sheet range: Optional cell range in A1 notation (e.g., 'A1:C10'). If not provided, gets all data. include_grid_data: If True, includes cell formatting and other metadata in the response. Note: Setting this to True will significantly increase the response size and token usage when parsing the response, as it includes detailed cell formatting information. Default is False (returns values only, more efficient). Returns: Grid data structure with either full metadata or just values from Google Sheets API, depending on include_grid_data parameter |
| `google-sheet get-sheet-formulas` | `{spreadsheet_id: str, sheet: str, range?: str = null}` | Get formulas from a specific sheet in a Google Spreadsheet. Args: spreadsheet_id: The ID of the spreadsheet (found in the URL) sheet: The name of the sheet range: Optional cell range in A1 notation (e.g., 'A1:C10'). If not provided, gets all formulas from the sheet. Returns: A 2D array of the sheet formulas. |
| `google-sheet update-cells` | `{spreadsheet_id: str, sheet: str, range: str, data: list[list]}` | Update cells in a Google Spreadsheet. Args: spreadsheet_id: The ID of the spreadsheet (found in the URL) sheet: The name of the sheet range: Cell range in A1 notation (e.g., 'A1:C10') data: 2D array of values to update Returns: Result of the update operation |
| `google-sheet batch-update-cells` | `{spreadsheet_id: str, sheet: str, ranges: dict}` | Batch update multiple ranges in a Google Spreadsheet. Args: spreadsheet_id: The ID of the spreadsheet (found in the URL) sheet: The name of the sheet ranges: Dictionary mapping range strings to 2D arrays of values e.g., {'A1:B2': [[1, 2], [3, 4]], 'D1:E2': [['a', 'b'], ['c', 'd']]} Returns: Result of the batch update operation |
| `google-sheet add-rows` | `{spreadsheet_id: str, sheet: str, count: int, start_row?: int = null}` | Add rows to a sheet in a Google Spreadsheet. Args: spreadsheet_id: The ID of the spreadsheet (found in the URL) sheet: The name of the sheet count: Number of rows to add start_row: 0-based row index to start adding. If not provided, adds at the beginning. Returns: Result of the operation |
| `google-sheet add-columns` | `{spreadsheet_id: str, sheet: str, count: int, start_column?: int = null}` | Add columns to a sheet in a Google Spreadsheet. Args: spreadsheet_id: The ID of the spreadsheet (found in the URL) sheet: The name of the sheet count: Number of columns to add start_column: 0-based column index to start adding. If not provided, adds at the beginning. Returns: Result of the operation |
| `google-sheet list-sheets` | `{spreadsheet_id: str}` | List all sheets in a Google Spreadsheet. Args: spreadsheet_id: The ID of the spreadsheet (found in the URL) Returns: List of sheet names |
| `google-sheet copy-sheet` | `{src_spreadsheet: str, src_sheet: str, dst_spreadsheet: str, dst_sheet: str}` | Copy a sheet from one spreadsheet to another. Args: src_spreadsheet: Source spreadsheet ID src_sheet: Source sheet name dst_spreadsheet: Destination spreadsheet ID dst_sheet: Destination sheet name Returns: Result of the operation |
| `google-sheet rename-sheet` | `{spreadsheet: str, sheet: str, new_name: str}` | Rename a sheet in a Google Spreadsheet. Args: spreadsheet: Spreadsheet ID sheet: Current sheet name new_name: New sheet name Returns: Result of the operation |
| `google-sheet get-multiple-sheet-data` | `{queries: list[dict]}` | Get data from multiple specific ranges in Google Spreadsheets. Args: queries: A list of dictionaries, each specifying a query. Each dictionary should have 'spreadsheet_id', 'sheet', and 'range' keys. Example: [{'spreadsheet_id': 'abc', 'sheet': 'Sheet1', 'range': 'A1:B5'}, {'spreadsheet_id': 'xyz', 'sheet': 'Data', 'range': 'C1:C10'}] Returns: A list of dictionaries, each containing the original query parameters and the fetched 'data' or an 'error'. |
| `google-sheet get-multiple-spreadsheet-summary` | `{spreadsheet_ids: list[str], rows_to_fetch?: int = 5}` | Get a summary of multiple Google Spreadsheets, including sheet names, headers, and the first few rows of data for each sheet. Args: spreadsheet_ids: A list of spreadsheet IDs to summarize. rows_to_fetch: The number of rows (including header) to fetch for the summary (default: 5). Returns: A list of dictionaries, each representing a spreadsheet summary. Includes spreadsheet title, sheet summaries (title, headers, first rows), or an error. |
| `google-sheet create-spreadsheet` | `{title: str, folder_id?: str = null}` | Create a new Google Spreadsheet. Args: title: The title of the new spreadsheet folder_id: Optional Google Drive folder ID where the spreadsheet should be created. If not provided, uses the configured default folder or creates in root. Returns: Information about the newly created spreadsheet including its ID |
| `google-sheet create-sheet` | `{spreadsheet_id: str, title: str}` | Create a new sheet tab in an existing Google Spreadsheet. Args: spreadsheet_id: The ID of the spreadsheet title: The title for the new sheet Returns: Information about the newly created sheet |
| `google-sheet list-spreadsheets` | `{folder_id?: str = null}` | List all spreadsheets in the specified Google Drive folder. If no folder is specified, uses the configured default folder or lists from 'My Drive'. Args: folder_id: Optional Google Drive folder ID to search in. If not provided, uses the configured default folder or searches 'My Drive'. Returns: List of spreadsheets with their ID and title |
| `google-sheet share-spreadsheet` | `{spreadsheet_id: str, recipients: list[dict], send_notification?: bool = true}` | Share a Google Spreadsheet with multiple users via email, assigning specific roles. Args: spreadsheet_id: The ID of the spreadsheet to share. recipients: A list of dictionaries, each containing 'email_address' and 'role'. The role should be one of: 'reader', 'commenter', 'writer'. Example: [ {'email_address': 'user1@example.com', 'role': 'writer'}, {'email_address': 'user2@example.com', 'role': 'reader'} ] send_notification: Whether to send a notification email to the users. Defaults to True. Returns: A dictionary containing lists of 'successes' and 'failures'. Each item in the lists includes the email address and the outcome. |
| `google-sheet list-folders` | `{parent_folder_id?: str = null}` | List all folders in the specified Google Drive folder. If no parent folder is specified, lists folders from 'My Drive' root. Args: parent_folder_id: Optional Google Drive folder ID to search within. If not provided, searches the root of 'My Drive'. Returns: List of folders with their ID, name, and parent information |
| `google-sheet search-spreadsheets` | `{query: str, max_results?: int = 20}` | Search for spreadsheets in Google Drive by name or content. Args: query: Search query string. Searches in file name and content. Examples: "budget 2024", "sales report", "project tracker" max_results: Maximum number of results to return (default 20, max 100) Returns: List of matching spreadsheets with their ID, name, and metadata |
| `google-sheet find-in-spreadsheet` | `{spreadsheet_id: str, query: str, sheet?: str = null, case_sensitive?: bool = false, max_results?: int = 50}` | Find cells containing a specific value in a Google Spreadsheet. Args: spreadsheet_id: The ID of the spreadsheet (found in the URL) query: The text to search for in cell values sheet: Optional sheet name to search in. If not provided, searches all sheets. case_sensitive: Whether the search should be case-sensitive (default False) max_results: Maximum number of results to return (default 50) Returns: List of found cells with their location (sheet, cell in A1 notation) and value |
| `google-sheet batch-update` | `{spreadsheet_id: str, requests: list[dict]}` | Execute a batch update on a Google Spreadsheet using the full batchUpdate endpoint. This provides access to all batchUpdate operations including adding sheets, updating properties, inserting/deleting dimensions, formatting, and more. Args: spreadsheet_id: The ID of the spreadsheet (found in the URL) requests: A list of request objects. Each request object can contain any valid batchUpdate operation. Common operations include: - addSheet: Add a new sheet - updateSheetProperties: Update sheet properties (title, grid properties, etc.) - insertDimension: Insert rows or columns - deleteDimension: Delete rows or columns - updateCells: Update cell values and formatting - updateBorders: Update cell borders - addConditionalFormatRule: Add conditional formatting - deleteConditionalFormatRule: Remove conditional formatting - updateDimensionProperties: Update row/column properties - and many more... Example requests: [ { "addSheet": { "properties": { "title": "New Sheet" } } }, { "updateSheetProperties": { "properties": { "sheetId": 0, "title": "Renamed Sheet" }, "fields": "title" } }, { "insertDimension": { "range": { "sheetId": 0, "dimension": "ROWS", "startIndex": 1, "endIndex": 3 } } } ] Returns: Result of the batch update operation, including replies for each request |
| `google-sheet add-chart` | `{spreadsheet_id: str, sheet: str, chart_type: str, data_range: str, title?: str = null, x_axis_label?: str = null, y_axis_label?: str = null, position_x?: int = 0, position_y?: int = 0, width?: int = 600, height?: int = 400}` | Add a chart to a Google Spreadsheet. Creates a chart from the specified data range with customizable type, title, and positioning. The chart is added as a floating element on the sheet. Args: spreadsheet_id: The ID of the spreadsheet (found in the URL) sheet: The name of the sheet containing the data chart_type: Type of chart to create. Supported types: - COLUMN: Vertical bar chart - BAR: Horizontal bar chart - LINE: Line chart - AREA: Area chart - PIE: Pie chart - SCATTER: Scatter plot - COMBO: Combination chart - HISTOGRAM: Histogram data_range: A1 notation range for chart data (e.g., 'A1:C10'). The first row is typically treated as headers. title: Optional title for the chart x_axis_label: Optional label for the X axis (bottom axis) y_axis_label: Optional label for the Y axis (left axis) position_x: Horizontal position offset in pixels from the top-left corner (default: 0) position_y: Vertical position offset in pixels from the top-left corner (default: 0) width: Width of the chart in pixels (default: 600) height: Height of the chart in pixels (default: 400) Returns: Result of the chart creation operation Examples: Create a column chart showing sales data: add_chart( spreadsheet_id="abc123", sheet="Sales", chart_type="COLUMN", data_range="A1:B13", title="Monthly Sales", x_axis_label="Month", y_axis_label="Revenue ($)" ) Create a pie chart for market share: add_chart( spreadsheet_id="abc123", sheet="Market", chart_type="PIE", data_range="A1:B5", title="Market Share by Product" ) |

## excel

Use `excel <command> '<JSON arguments>'`. Run `excel <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `excel apply-formula` | `{filepath: str, sheet_name: str, cell: str, formula: str}` | Apply Excel formula to cell. Excel formula will write to cell with verification. |
| `excel validate-formula-syntax` | `{filepath: str, sheet_name: str, cell: str, formula: str}` | Validate Excel formula syntax without applying it. |
| `excel format-range` | `{filepath: str, sheet_name: str, start_cell: str, end_cell?: str = null, bold?: bool = false, italic?: bool = false, underline?: bool = false, font_size?: int = null, font_color?: str = null, bg_color?: str = null, border_style?: str = null, border_color?: str = null, number_format?: str = null, alignment?: str = null, wrap_text?: bool = false, merge_cells?: bool = false, protection?: dict = null, conditional_format?: dict = null}` | Apply formatting to a range of cells. |
| `excel read-data-from-excel` | `{filepath: str, sheet_name: str, start_cell?: str = "A1", end_cell?: str = null, preview_only?: bool = false}` | Read data from Excel worksheet with cell metadata including validation rules. Args: filepath: Path to Excel file sheet_name: Name of worksheet start_cell: Starting cell (default A1) end_cell: Ending cell (optional, auto-expands if not provided) preview_only: Whether to return preview only Returns: JSON string containing structured cell data with validation metadata. Each cell includes: address, value, row, column, and validation info (if any). |
| `excel write-data-to-excel` | `{filepath: str, sheet_name: str, data: list[list], start_cell?: str = "A1"}` | Write data to Excel worksheet. Excel formula will write to cell without any verification. PARAMETERS: filepath: Path to Excel file sheet_name: Name of worksheet to write to data: List of lists containing data to write to the worksheet, sublists are assumed to be rows start_cell: Cell to start writing to, default is "A1" |
| `excel create-workbook` | `{filepath: str}` | Create new Excel workbook. |
| `excel create-worksheet` | `{filepath: str, sheet_name: str}` | Create new worksheet in workbook. |
| `excel create-chart` | `{filepath: str, sheet_name: str, data_range: str, chart_type: str, target_cell: str, title?: str = "", x_axis?: str = "", y_axis?: str = ""}` | Create chart in worksheet. |
| `excel create-pivot-table` | `{filepath: str, sheet_name: str, data_range: str, rows: list[str], values: list[str], columns?: list[str] = null, agg_func?: str = "mean"}` | Create pivot table in worksheet. |
| `excel create-table` | `{filepath: str, sheet_name: str, data_range: str, table_name?: str = null, table_style?: str = "TableStyleMedium9"}` | Creates a native Excel table from a specified range of data. |
| `excel copy-worksheet` | `{filepath: str, source_sheet: str, target_sheet: str}` | Copy worksheet within workbook. |
| `excel delete-worksheet` | `{filepath: str, sheet_name: str}` | Delete worksheet from workbook. |
| `excel rename-worksheet` | `{filepath: str, old_name: str, new_name: str}` | Rename worksheet in workbook. |
| `excel get-workbook-metadata` | `{filepath: str, include_ranges?: bool = false}` | Get metadata about workbook including sheets, ranges, etc. |
| `excel merge-cells` | `{filepath: str, sheet_name: str, start_cell: str, end_cell: str}` | Merge a range of cells. |
| `excel unmerge-cells` | `{filepath: str, sheet_name: str, start_cell: str, end_cell: str}` | Unmerge a range of cells. |
| `excel copy-range` | `{filepath: str, sheet_name: str, source_start: str, source_end: str, target_start: str, target_sheet?: str = null}` | Copy a range of cells to another location. |
| `excel delete-range` | `{filepath: str, sheet_name: str, start_cell: str, end_cell: str, shift_direction?: str = "up"}` | Delete a range of cells and shift remaining cells. |
| `excel validate-excel-range` | `{filepath: str, sheet_name: str, start_cell: str, end_cell?: str = null}` | Validate if a range exists and is properly formatted. |
| `excel get-data-validation-info` | `{filepath: str, sheet_name: str}` | Get all data validation rules in a worksheet. This tool helps identify which cell ranges have validation rules and what types of validation are applied. Args: filepath: Path to Excel file sheet_name: Name of worksheet Returns: JSON string containing all validation rules in the worksheet |

## git

Use `git --help` for Git operations on workspace repositories.

## python3

Execute Python code directly under the agent workspace and return stdout
and stderr. Code can be pasted into a `.py` file and run with `python3`.

Python cannot launch subprocesses or make direct network requests. Run the
documented service commands directly in the shell. Use Python for local
file processing and generating JSON arguments.
