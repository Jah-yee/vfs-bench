---
name: workspace-commands
description: The shell commands and task tools available in this workspace.
---

# Available commands

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip  curl

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## web-search

Use `web-search <command> '<JSON arguments>'`. Run
`web-search <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `web-search web-search` | `{query: str, num_results?: int = 10}` | Search the web using Google Serper API with concurrency control and retry mechanisms. Supports various Google search operators. — `query`: Search query with optional Google search operators.; `num_results`: Number of results to return, default 10, max 50 |

## browser

Use `browser <command> '<JSON arguments>'`. Run `browser <command> --help`
to get more information.

| Command | Arguments | Description |
|---|---|---|
| `browser close` | `{}` | Close the page |
| `browser resize` | `{width: number, height: number}` | Resize the browser window — `width`: Width of the browser window; `height`: Height of the browser window |
| `browser console-messages` | `{}` | Returns all console messages |
| `browser handle-dialog` | `{accept: bool, promptText?: str}` | Handle a dialog — `accept`: Whether to accept the dialog.; `promptText`: The text of the prompt in case of a prompt dialog. |
| `browser evaluate` | `{function: str, element?: str, ref?: str}` | Evaluate JavaScript expression on page or element — `function`: () => { /* code */ } or (element) => { /* code */ } when element is provided; `element`: Human-readable element description used to obtain permission to interact with the element; `ref`: Exact target element reference from the page snapshot |
| `browser file-upload` | `{paths: list[str]}` | Upload one or multiple files — `paths`: The absolute paths to the files to upload. Can be a single file or multiple files. |
| `browser install` | `{}` | Install the browser specified in the config. Call this if you get an error about the browser not being installed. |
| `browser press-key` | `{key: str}` | Press a key on the keyboard — `key`: Name of the key to press or a character to generate, such as `ArrowLeft` or `a` |
| `browser type` | `{element: str, ref: str, text: str, submit?: bool, slowly?: bool}` | Type text into editable element — `element`: Human-readable element description used to obtain permission to interact with the element; `ref`: Exact target element reference from the page snapshot; `text`: Text to type into the element; `submit`: Whether to submit entered text (press Enter after); `slowly`: Whether to type one character at a time. Useful for triggering key handlers in the page. By default entire text is filled in at once. |
| `browser navigate` | `{url: str}` | Navigate to a URL — `url`: The URL to navigate to |
| `browser navigate-back` | `{}` | Go back to the previous page |
| `browser navigate-forward` | `{}` | Go forward to the next page |
| `browser network-requests` | `{}` | Returns all network requests since loading the page |
| `browser take-screenshot` | `{raw?: bool, filename?: str, element?: str, ref?: str, fullPage?: bool}` | Take a screenshot of the current page. You can't perform actions based on the screenshot, use browser_snapshot for actions. — `raw`: Whether to return without compression (in PNG format). Default is false, which returns a JPEG image.; `filename`: File name to save the screenshot to. Defaults to `page-{timestamp}.{png\|jpeg}` if not specified.; `element`: Human-readable element description used to obtain permission to screenshot the element. If not provided, the screenshot will be taken of viewport. If element is provided, ref must be provided too.; `ref`: Exact target element reference from the page snapshot. If not provided, the screenshot will be taken of viewport. If ref is provided, element must be provided too.; `fullPage`: When true, takes a screenshot of the full scrollable page, instead of the currently visible viewport. Cannot be used with element screenshots. |
| `browser snapshot` | `{}` | Capture accessibility snapshot of the current page. The snapshot is divided into manageable spans (configurable via --span-size, default 2000 characters, or use -1 to show complete snapshot) and shows the first span by default. Use browser_snapshot_navigate_* tools to view other spans or browser_snapshot_search to find content across all spans. This provides structured element data with ref attributes for interaction, making it better than screenshots for automation. |
| `browser click` | `{element: str, ref: str, doubleClick?: bool, button?: "left" \| "right" \| "middle"}` | Perform click on a web page — `element`: Human-readable element description used to obtain permission to interact with the element; `ref`: Exact target element reference from the page snapshot; `doubleClick`: Whether to perform a double click instead of a single click; `button`: Button to click, defaults to left |
| `browser drag` | `{startElement: str, startRef: str, endElement: str, endRef: str}` | Perform drag and drop between two elements — `startElement`: Human-readable source element description used to obtain the permission to interact with the element; `startRef`: Exact source element reference from the page snapshot; `endElement`: Human-readable target element description used to obtain the permission to interact with the element; `endRef`: Exact target element reference from the page snapshot |
| `browser hover` | `{element: str, ref: str}` | Hover over element on page — `element`: Human-readable element description used to obtain permission to interact with the element; `ref`: Exact target element reference from the page snapshot |
| `browser select-option` | `{element: str, ref: str, values: list[str]}` | Select an option in a dropdown — `element`: Human-readable element description used to obtain permission to interact with the element; `ref`: Exact target element reference from the page snapshot; `values`: Array of values to select in the dropdown. This can be a single value or multiple values. |
| `browser snapshot-navigate-to-span` | `{spanIndex: int}` | Navigate to a specific span in the current page snapshot by index. Each span contains a portion of the page content (limited by span size). Use this when you know the exact span number you want to view, typically after using browser_snapshot_search to locate content. — `spanIndex`: The span index to navigate to (0-based) |
| `browser snapshot-navigate-to-first-span` | `{}` | Navigate to the first span of the current page snapshot. This shows the beginning of the page content and is useful for starting from the top of the page when exploring content sequentially. |
| `browser snapshot-navigate-to-last-span` | `{}` | Navigate to the last span of the current page snapshot. This shows the end of the page content and is useful for accessing footer content, final form elements, or bottom navigation. |
| `browser snapshot-navigate-to-next-span` | `{}` | Navigate to the next span in the current page snapshot. If already at the last span, stays at the last span. Use this for sequential exploration of page content from top to bottom. |
| `browser snapshot-navigate-to-prev-span` | `{}` | Navigate to the previous span in the current page snapshot. If already at the first span, stays at the first span. Use this for sequential exploration of page content from bottom to top. |
| `browser snapshot-navigate-to-line` | `{globalLineNumber: int, contextLines?: int}` | Navigate to a specific global line number in the current page snapshot with configurable surrounding context lines. Shows which spans contain the context lines. The target line is marked with ">>>". Use this to quickly jump to specific content found via search results. — `globalLineNumber`: The global line number to navigate to (1-based); `contextLines`: Number of context lines to show before and after the target line (default: 3) |
| `browser snapshot-search` | `{pattern: str, flags?: str}` | Search for a pattern across all spans of the current page snapshot using regular expressions. Returns matches with both global line numbers (across entire snapshot) and in-span line numbers (within each span). Shows which spans contain matches for navigation. Supports regex flags like "gi" for global case-insensitive search. — `pattern`: The regex pattern to search for; `flags`: Optional regex flags (e.g., "gi" for global case-insensitive) |
| `browser tab-list` | `{}` | List browser tabs |
| `browser tab-new` | `{url?: str}` | Open a new tab — `url`: The URL to navigate to in the new tab. If not provided, the new tab will be blank. |
| `browser tab-select` | `{index: number}` | Select a tab by index — `index`: The index of the tab to select |
| `browser tab-close` | `{index?: number}` | Close a tab — `index`: The index of the tab to close. Closes current tab if not provided. |
| `browser wait-for` | `{time?: number, text?: str, textGone?: str}` | Wait for text to appear or disappear or a specified time to pass — `time`: The time to wait in seconds; `text`: The text to wait for; `textGone`: The text to wait for to disappear |

## fetch

Use `fetch <command> '<JSON arguments>'`. Run `fetch <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `fetch html` | `{url: str, headers?: dict}` | Fetch a website and return the content as HTML — `url`: URL of the website to fetch; `headers`: Optional headers to include in the request |
| `fetch markdown` | `{url: str, headers?: dict}` | Fetch a website and return the content as Markdown — `url`: URL of the website to fetch; `headers`: Optional headers to include in the request |
| `fetch txt` | `{url: str, headers?: dict}` | Fetch a website, return the content as plain text (no HTML) — `url`: URL of the website to fetch; `headers`: Optional headers to include in the request |
| `fetch json` | `{url: str, headers?: dict}` | Fetch a JSON file from a URL — `url`: URL of the JSON to fetch; `headers`: Optional headers to include in the request |

## arxiv-local

Use `arxiv-local <command> '<JSON arguments>'`. Run
`arxiv-local <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `arxiv-local search-papers` | `{query: str, max_results?: int, date_from?: str, date_to?: str, categories?: list[str]}` | Search for papers on arXiv with advanced filtering |
| `arxiv-local download-paper` | `{paper_id: str, check_status?: bool = false}` | Download a paper and create a resource for it — `paper_id`: The arXiv ID of the paper to download; `check_status`: If true, only check conversion status without downloading |
| `arxiv-local list-papers` | `{}` | List all existing papers available as resources |
| `arxiv-local read-paper` | `{paper_id: str}` | Read the full content of a stored paper in markdown format — `paper_id`: The arXiv ID of the paper to read |

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
