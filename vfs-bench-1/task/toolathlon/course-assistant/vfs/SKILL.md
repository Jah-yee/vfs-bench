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

## emails

Use `emails <command> '<JSON arguments>'`. Run `emails <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `emails get-emails` | `{folder?: str = "INBOX", page?: int = 1, page_size?: int = 20}` | Get paginated list of emails from specified folder Args: folder: Email folder name (default: INBOX) page: Page number starting from 1 (default: 1) page_size: Number of emails per page (default: 20) |
| `emails read-email` | `{email_id: str}` | Read full content of a specific email Args: email_id: Email ID to read |
| `emails search-emails` | `{query: str, folder?: str = "INBOX", page?: int = 1, page_size?: int = 20}` | Search emails with query string (sorted by date descending) Args: query: Search query (subject, from, body content) folder: Folder to search in (default: INBOX) page: Page number starting from 1 (default: 1) page_size: Number of results per page (default: 20) |
| `emails send-email` | `{to: str, subject: str, body: str, html_body?: str = null, cc?: str = null, bcc?: str = null, attachments?: list[str] = null}` | Send an email with optional HTML body, CC, BCC, and attachments Args: to: Recipient email address(es), comma-separated subject: Email subject body: Plain text body html_body: HTML body content (optional) cc: CC recipients, comma-separated (optional) bcc: BCC recipients, comma-separated (optional) attachments: List of file paths to attach (optional) |
| `emails reply-email` | `{email_id: str, body: str, html_body?: str = null, cc?: str = null, bcc?: str = null, reply_all?: bool = false}` | Reply to an email Args: email_id: ID of email to reply to body: Reply message body (plain text) html_body: Reply message body (HTML, optional) cc: Additional CC recipients (optional) bcc: BCC recipients (optional) reply_all: Whether to reply to all recipients (default: False) |
| `emails forward-email` | `{email_id: str, to: str, body?: str = null, html_body?: str = null, cc?: str = null, bcc?: str = null}` | Forward an email to other recipients Args: email_id: ID of email to forward to: Recipients to forward to body: Additional message body (optional) html_body: Additional HTML message body (optional) cc: CC recipients (optional) bcc: BCC recipients (optional) |
| `emails delete-email` | `{email_id: str}` | Delete an email Args: email_id: Email ID to delete |
| `emails move-email` | `{email_id: str, target_folder: str}` | Move email to another folder Args: email_id: Email ID to move target_folder: Target folder name |
| `emails mark-emails` | `{email_ids: list[str], status: str}` | Mark multiple emails with status (read/unread/important/not_important) Args: email_ids: List of email IDs to mark status: Status to set (read, unread, important, not_important) |
| `emails move-emails` | `{email_ids: list[str], target_folder: str}` | Move multiple emails to another folder with improved ID synchronization Args: email_ids: List of email IDs to move target_folder: Target folder name |
| `emails delete-emails` | `{email_ids: list[str]}` | Delete multiple emails with improved ID synchronization Args: email_ids: List of email IDs to delete |
| `emails get-folders` | `{}` | Get list of available email folders |
| `emails create-folder` | `{folder_name: str}` | Create new email folder Args: folder_name: Name of folder to create |
| `emails delete-folder` | `{folder_name: str}` | Delete email folder Args: folder_name: Name of folder to delete |
| `emails get-mailbox-stats` | `{folder_name?: str = null}` | Get mailbox statistics Args: folder_name: Specific folder name (optional, defaults to all folders) |
| `emails get-unread-count` | `{folder_name?: str = null}` | Get unread message count Args: folder_name: Specific folder name (optional, defaults to all folders) |
| `emails check-connection` | `{}` | Check email server connection status |
| `emails get-email-headers` | `{email_id: str}` | Get complete email headers for technical analysis Args: email_id: Email ID to get headers for |
| `emails save-draft` | `{subject: str, body: str, html_body?: str = null, to?: str = null, cc?: str = null, bcc?: str = null}` | Save email draft Args: subject: Email subject body: Plain text body html_body: HTML body content (optional) to: Recipient email address(es) (optional) cc: CC recipients (optional) bcc: BCC recipients (optional) |
| `emails get-drafts` | `{page?: int = 1, page_size?: int = 20}` | Get list of saved drafts Args: page: Page number starting from 1 (default: 1) page_size: Number of drafts per page (default: 20) |
| `emails update-draft` | `{draft_id: str, subject?: str = null, body?: str = null, html_body?: str = null, to?: str = null, cc?: str = null, bcc?: str = null}` | Update existing draft Args: draft_id: Draft ID to update subject: Email subject (optional) body: Plain text body (optional) html_body: HTML body content (optional) to: Recipient email address(es) (optional) cc: CC recipients (optional) bcc: BCC recipients (optional) |
| `emails delete-draft` | `{draft_id: str}` | Delete draft Args: draft_id: Draft ID to delete |
| `emails export-emails` | `{folder?: str = null, export_path?: str = "emails_export.json", max_emails?: int = null, export_all_folders?: bool = false}` | Export emails to file for backup Args: folder: Specific folder to export (mutually exclusive with export_all_folders) export_path: Path where to save the export file max_emails: Maximum number of emails to export (optional, exports all if not specified) export_all_folders: Export from all folders instead of just one (default: False) |
| `emails import-emails` | `{import_path: str, target_folder?: str = null, preserve_folders?: bool = true}` | Import emails from backup file to IMAP server Args: import_path: Path to import file (.json or .eml) or a directory target_folder: Target folder for imported emails (if preserve_folders=False) preserve_folders: Whether to preserve original folder structure (default: True) |
| `emails download-attachment` | `{email_id: str, attachment_filename: str}` | Download email attachment to configured download path Args: email_id: Email ID containing the attachment attachment_filename: Name of attachment to download |

## git

Use `git --help` for Git operations on workspace repositories.

## python3

Execute Python code directly under the agent workspace and return stdout
and stderr. Code can be pasted into a `.py` file and run with `python3`.

Python cannot launch subprocesses or make direct network requests. Run the
documented service commands directly in the shell. Use Python for local
file processing and generating JSON arguments.
