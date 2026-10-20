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
