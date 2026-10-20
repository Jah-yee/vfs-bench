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

## memory

Use `memory <command> '<JSON arguments>'`. Run `memory <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `memory create-entities` | `{entities: list[{name: str, entityType: str, observations: list[str]}]}` | Create multiple new entities in the knowledge graph — `entities.name`: The name of the entity; `entities.entityType`: The type of the entity; `entities.observations`: An array of observation contents associated with the entity |
| `memory create-relations` | `{relations: list[{from: str, to: str, relationType: str}]}` | Create multiple new relations between entities in the knowledge graph. Relations should be in active voice — `relations.from`: The name of the entity where the relation starts; `relations.to`: The name of the entity where the relation ends; `relations.relationType`: The type of the relation |
| `memory add-observations` | `{observations: list[{entityName: str, contents: list[str]}]}` | Add new observations to existing entities in the knowledge graph — `observations.entityName`: The name of the entity to add the observations to; `observations.contents`: An array of observation contents to add |
| `memory delete-entities` | `{entityNames: list[str]}` | Delete multiple entities and their associated relations from the knowledge graph — `entityNames`: An array of entity names to delete |
| `memory delete-observations` | `{deletions: list[{entityName: str, observations: list[str]}]}` | Delete specific observations from entities in the knowledge graph — `deletions.entityName`: The name of the entity containing the observations; `deletions.observations`: An array of observations to delete |
| `memory delete-relations` | `{relations: list[{from: str, to: str, relationType: str}]}` | Delete multiple relations from the knowledge graph — `relations`: An array of relations to delete; `relations.from`: The name of the entity where the relation starts; `relations.to`: The name of the entity where the relation ends; `relations.relationType`: The type of the relation |
| `memory read-graph` | `{}` | Read the entire knowledge graph |
| `memory search-nodes` | `{query: str}` | Search for nodes in the knowledge graph based on a query — `query`: The search query to match against entity names, types, and observation content |
| `memory open-nodes` | `{names: list[str]}` | Open specific nodes in the knowledge graph by their names — `names`: An array of entity names to retrieve |
