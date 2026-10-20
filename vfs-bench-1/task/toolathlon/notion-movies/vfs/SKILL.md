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

## notion

Use `notion <command> '<JSON arguments>'`. Run `notion <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `notion get-user` | `{user_id: str}` | Notion \| Retrieve a user |
| `notion get-users` | `{start_cursor?: str, page_size?: int = 100}` | Notion \| List all users — `start_cursor`: If supplied, this endpoint will return a page of results starting after the cursor provided. If not supplied, this endpoint will return the first page of results.; `page_size`: The number of items from the full list desired in the response. Maximum: 100 |
| `notion get-self` | `{}` | Notion \| Retrieve your token's bot user |
| `notion post-database-query` | `{database_id: str, filter_properties?: list[str], filter?: dict, sorts?: list[{property: str, direction: "ascending" \| "descending"}], start_cursor?: str, page_size?: int = 100, archived?: bool, in_trash?: bool}` | Notion \| Query a database — `database_id`: Identifier for a Notion database.; `filter_properties`: A list of page property value IDs associated with the database. Use this param to limit the response to a specific page property value or values for pages that meet the `filter` criteria.; `filter`: When supplied, limits which pages are returned based on the [filter conditions](ref:post-database-query-filter).; `sorts`: When supplied, orders the results based on the provided [sort criteria](ref:post-database-query-sort).; `start_cursor`: When supplied, returns a page of results starting after the cursor provided. If not supplied, this endpoint will return the first page of results.; `page_size`: The number of items from the full list desired in the response. Maximum: 100 |
| `notion post-search` | `{query?: str, sort?: {direction?: str, timestamp?: str}, filter?: {value?: str, property?: str}, start_cursor?: str, page_size?: int = 100}` | Notion \| Search by title — `query`: The text that the API compares page and database titles against.; `sort`: A set of criteria, `direction` and `timestamp` keys, that orders the results. The **only** supported timestamp value is `"last_edited_time"`. Supported `direction` values are `"ascending"` and `"descending"`. If `sort` is not provided, then the most recently edited results are returned first.; `sort.direction`: The direction to sort. Possible values include `ascending` and `descending`.; `sort.timestamp`: The name of the timestamp to sort against. Possible values include `last_edited_time`.; `filter`: A set of criteria, `value` and `property` keys, that limits the results to either only pages or only databases. Possible `value` values are `"page"` or `"database"`. The only supported `property` value is `"object"`.; `filter.value`: The value of the property to filter the results by. Possible values for object type include `page` or `database`. **Limitation**: Currently the only filter allowed is `object` which will filter by type of object (either `page` or `database`); `filter.property`: The name of the property to filter by. Currently the only property you can filter by is the object type. Possible values include `object`. Limitation: Currently the only filter allowed is `object` which will filter by type of object (either `page` or `database`); `start_cursor`: A `cursor` value returned in a previous response that If supplied, limits the response to results starting after the `cursor`. If not supplied, then the first page of results is returned. Refer to [pagination](https://developers.notion.com/reference/intro#pagination) for more details.; `page_size`: The number of items from the full list to include in the response. Maximum: `100`. |
| `notion get-block-children` | `{block_id: str, start_cursor?: str, page_size?: int = 100}` | Notion \| Retrieve block children — `block_id`: Identifier for a [block](ref:block); `start_cursor`: If supplied, this endpoint will return a page of results starting after the cursor provided. If not supplied, this endpoint will return the first page of results.; `page_size`: The number of items from the full list desired in the response. Maximum: 100 |
| `notion patch-block-children` | `{block_id: str, children: list[{paragraph?: {rich_text: list[{text: {content: str, link?: dict \| null}, type?: "text"}]}, bulleted_list_item?: {rich_text: list[{text: {content: str, link?: dict \| null}, type?: "text"}]}, type?: "paragraph" \| "bulleted_list_item"}], after?: str}` | Notion \| Append block children — `block_id`: Identifier for a [block](ref:block). Also accepts a [page](ref:page) ID.; `children`: Child content to append to a container block as an array of [block objects](ref:block); `after`: The ID of the existing block that the new block should be appended after. |
| `notion retrieve-a-block` | `{block_id: str}` | Notion \| Retrieve a block — `block_id`: Identifier for a Notion block |
| `notion update-a-block` | `{block_id: str, type?: dict, archived?: bool = true}` | Notion \| Update a block — `block_id`: Identifier for a Notion block; `type`: The [block object `type`](ref:block#block-object-keys) value with the properties to be updated. Currently only `text` (for supported block types) and `checked` (for `to_do` blocks) fields can be updated.; `archived`: Set to true to archive (delete) a block. Set to false to un-archive (restore) a block. |
| `notion delete-a-block` | `{block_id: str}` | Notion \| Delete a block — `block_id`: Identifier for a Notion block |
| `notion retrieve-a-page` | `{page_id: str, filter_properties?: str}` | Notion \| Retrieve a page — `page_id`: Identifier for a Notion page; `filter_properties`: A list of page property value IDs associated with the page. Use this param to limit the response to a specific page property value or values. To retrieve multiple properties, specify each page property ID. For example: `?filter_properties=iAk8&filter_properties=b7dh`. |
| `notion patch-page` | `{page_id: str, properties?: dict, in_trash?: bool = false, archived?: bool, icon?: {emoji: str}, cover?: {external: {url: str}, type?: "external"}}` | Notion \| Update page properties — `page_id`: The identifier for the Notion page to be updated.; `properties`: Property values to update. Keys are property names or IDs; values are property value objects. Title is no longer required.; `in_trash`: Set to true to delete a block. Set to false to restore a block.; `icon`: A page icon for the page. Supported types are [external file object](https://developers.notion.com/reference/file-object) or [emoji object](https://developers.notion.com/reference/emoji-object).; `cover`: A cover image for the page. Only [external file objects](https://developers.notion.com/reference/file-object) are supported. |
| `notion post-page` | `{parent: {page_id: str} \| {database_id: str, type?: any} \| {data_source_id: str, type?: any}, properties: dict, children?: list[str], icon?: str, cover?: str}` | Notion \| Create a page — `properties`: Property values for the new page. Keys are property names or IDs; values are property value objects.; `children`: The content to be rendered on the new page, represented as an array of [block objects](https://developers.notion.com/reference/block).; `icon`: The icon of the new page. Either an [emoji object](https://developers.notion.com/reference/emoji-object) or an [external file object](https://developers.notion.com/reference/file-object)..; `cover`: The cover image of the new page, represented as a [file object](https://developers.notion.com/reference/file-object). |
| `notion create-a-database` | `{parent: {type: "page_id", page_id: str}, properties: dict[str, {title: dict, description?: str}], title?: list[{text: {content: str, link?: dict \| null}, type?: "text"}]}` | Notion \| Create a database — `properties`: Property schema of database. The keys are the names of properties as they appear in Notion and the values are [property schema objects](https://developers.notion.com/reference/property-schema-object). |
| `notion update-a-database` | `{database_id: str, title?: list[{text: {content: str, link?: dict \| null}, type?: "text"}], description?: list[{text: {content: str, link?: dict \| null}, type?: "text"}], properties?: {name?: str}}` | Notion \| Update a database — `database_id`: identifier for a Notion database; `title`: An array of [rich text objects](https://developers.notion.com/reference/rich-text) that represents the title of the database that is displayed in the Notion UI. If omitted, then the database title remains unchanged.; `description`: An array of [rich text objects](https://developers.notion.com/reference/rich-text) that represents the description of the database that is displayed in the Notion UI. If omitted, then the database description remains unchanged.; `properties`: Property schema of database. The keys are the names of properties as they appear in Notion and the values are [property schema objects](https://developers.notion.com/reference/property-schema-object). |
| `notion retrieve-a-database` | `{database_id: str}` | Notion \| Retrieve a database — `database_id`: An identifier for the Notion database. |
| `notion retrieve-a-page-property` | `{page_id: str, property_id: str, page_size?: int, start_cursor?: str}` | Notion \| Retrieve a page property item — `page_id`: Identifier for a Notion page; `property_id`: Identifier for a page [property](https://developers.notion.com/reference/page#all-property-values); `page_size`: For paginated properties. The max number of property item objects on a page. The default size is 100; `start_cursor`: For paginated properties. |
| `notion retrieve-a-comment` | `{block_id: str, start_cursor?: str, page_size?: int}` | Notion \| Retrieve comments — `block_id`: Identifier for a Notion block or page; `start_cursor`: If supplied, this endpoint will return a page of results starting after the cursor provided. If not supplied, this endpoint will return the first page of results.; `page_size`: The number of items from the full list desired in the response. Maximum: 100 |
| `notion create-a-comment` | `{parent: {page_id: str}, rich_text: list[{text: {content: str}}]}` | Notion \| Create comment — `parent`: The page that contains the comment; `parent.page_id`: the page ID; `rich_text.text.content`: The content of the comment |
