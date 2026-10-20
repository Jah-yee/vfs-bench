---
name: workspace-commands
description: The shell commands and task tools available in this workspace.
---

# Available commands

Python (`python` or `python3`), Perl, JavaScript/Node.js, and TypeScript
runtimes are unavailable. Use the shell commands and task CLIs documented
below; do not probe for or attempt to install other runtimes.

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## kubectl

Use `kubectl --help` for Kubernetes reads and mutations against the task cluster. Use the original resource names, namespaces and selectors. Piped bytes reach stdin; file arguments under `/workspace` refer to task files.

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
