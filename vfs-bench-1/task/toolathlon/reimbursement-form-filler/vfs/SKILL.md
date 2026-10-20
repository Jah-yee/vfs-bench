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

## pdf-tools

Use `pdf-tools <command> '<JSON arguments>'`. Run
`pdf-tools <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `pdf-tools read-pdf-pages` | `{pdf_file_path: str, start_page?: int = 1, end_page?: int = 1}` | Read content from PDF file for specified page range. Supports both local file paths and URLs. For URLs, the PDF will be downloaded to a temporary directory and cached for future use. Note: Avoid reading too many pages at once (recommended: <50 pages) to prevent errors. Args: pdf_file_path: Path to the PDF file or URL to PDF start_page: Starting page number (default: 1) end_page: Ending page number (default: 1) Returns: Extracted text content from the specified pages |
| `pdf-tools get-pdf-info` | `{pdf_file_path: str}` | Get basic information about a PDF file including page count. Supports both local file paths and URLs. For URLs, the PDF will be downloaded to a temporary directory and cached for future use. Args: pdf_file_path: Path to the PDF file or URL to PDF Returns: Basic information about the PDF file |
| `pdf-tools merge-pdfs` | `{pdf_paths: list[str], output_path: str}` | Merge multiple PDF files into one. Supports both local file paths and URLs. URLs will be downloaded to temporary files before merging. Mixed local and URL paths are supported. Args: pdf_paths: List of paths to PDF files to merge (in order) - can include URLs output_path: Path where the merged PDF will be saved (must be local path) Returns: Success message with merge details or error message |
| `pdf-tools extract-pdf-pages` | `{source_path: str, page_numbers: list[int], output_path: str}` | Extract specific pages from a PDF and create a new PDF. Supports URLs for source PDF. The source PDF will be downloaded to a temporary directory if it's a URL. Output path must be a local file path. Args: source_path: Path to the source PDF file or URL to PDF page_numbers: List of page numbers to extract (1-indexed) output_path: Path where the new PDF will be saved (must be local path) Returns: Success message with extraction details or error message |
| `pdf-tools search-pdf-content` | `{pdf_file_path: str, pattern: str, page_size?: int = 10}` | Search for regex pattern in PDF content and return paginated results. Supports both local file paths and URLs. For URLs, the PDF will be downloaded to a temporary directory and cached for future use. Args: pdf_file_path: Path to the PDF file or URL to PDF pattern: Regular expression pattern to search for page_size: Number of results per page (10-50, default: 10) Returns: Search results with UUID for pagination, or error message |
| `pdf-tools search-pdf-next-page` | `{search_id: str}` | Get next page of search results. Args: search_id: Search session ID from previous search Returns: Next page of search results or error message |
| `pdf-tools search-pdf-prev-page` | `{search_id: str}` | Get previous page of search results. Args: search_id: Search session ID from previous search Returns: Previous page of search results or error message |
| `pdf-tools search-pdf-go-page` | `{search_id: str, page_number: int}` | Go to specific page of search results. Args: search_id: Search session ID from previous search page_number: Page number to go to (1-indexed) Returns: Specified page of search results or error message |
| `pdf-tools search-pdf-info` | `{search_id: str}` | Get information about a search session. Args: search_id: Search session ID from previous search Returns: Information about the search session |

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
