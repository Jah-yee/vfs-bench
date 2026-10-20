---
name: workspace-commands
description: Use when running commands in this workspace - which commands exist, what they can do, and what the interpreter supports.
---

# Available commands

Python (`python` or `python3`), Perl, JavaScript/Node.js, and TypeScript
runtimes are unavailable. Use the shell commands and task CLIs documented
below; do not probe for or attempt to install other runtimes.

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq

with pipes, `>` redirection and `$(...)` substitution.

Do not probe the machine with `which`, `type`, `--version`, `env`, `ps`,
`echo $PATH`, `ls /usr/bin` or `cat /usr/bin/<command>`: they tell you
nothing about the task.

A filename with a space in it needs quoting, as it would in any shell.

You can also use `git`.

## notion

Use `notion <command> '<JSON arguments>'`. Run `notion <command> --help` to
get more information.

```sh
notion post-database-query '{"database_id":"ID","filter":{"property":"Name","rich_text":{"contains":"TEXT"}},"page_size":10}'
notion post-search '{"query":"QUERY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `notion post-database-query` | `{database_id: str, filter_properties?: list[str], filter?: dict, sorts?: list[{property: str, direction: "ascending" \| "descending"}], start_cursor?: str, page_size?: int = 100, archived?: bool, in_trash?: bool}` | Query a database |
| `notion post-search` | `{query?: str, sort?: {direction?: str, timestamp?: str}, filter?: {value?: str, property?: str}, start_cursor?: str, page_size?: int = 100}` | Search by title |

## slack

Use `slack <command> '<JSON arguments>'`. Run `slack <command> --help` to
get more information.

```sh
slack conversations-replies '{"channel_id":"CHANNEL_ID","thread_ts":"1234567890.123456"}'
```

| Command | Arguments | Description |
|---|---|---|
| `slack conversations-replies` | `{channel_id: str, cursor?: str, include_activity_messages?: bool = false, limit?: str = "1d", thread_ts: str}` | Get a thread of messages posted to a conversation by channelID and thread_ts, the last row/column in the response is used as 'cursor' parameter for pagination if not empty |

## memory

Use `memory <command> '<JSON arguments>'`. Run `memory <command> --help` to
get more information.

```sh
memory search-nodes '{"query":"QUERY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `memory search-nodes` | `{query: str}` | Search for nodes in the knowledge graph based on a query |

## e2b-server

Use `e2b-server <command> '<JSON arguments>'`. Run
`e2b-server <command> --help` to get more information.

```sh
e2b-server run-code '{"code":"print(1 + 1)"}'
```

| Command | Arguments | Description |
|---|---|---|
| `e2b-server run-code` | `{code: str}` | Run python code in a secure sandbox by E2B. Using the Jupyter Notebook syntax. |

## met-museum

Use `met-museum <command> '<JSON arguments>'`. Run
`met-museum <command> --help` to get more information.

```sh
met-museum search-museum-objects '{"q":"QUERY","hasImages":true}'
```

| Command | Arguments | Description |
|---|---|---|
| `met-museum search-museum-objects` | `{q: str, hasImages?: bool = false, title?: bool = false, departmentId?: number}` | Search for objects in the Metropolitan Museum of Art (Met Museum). Will return Total objects found, followed by a list of Object Ids.The parameter title should be set to true if you want to search for objects by title.The parameter hasImages is false by default, but can be set to true to return objects without images.If the parameter hasImages is true, the parameter title should be false. |

## national-parks

Use `national-parks <command> '<JSON arguments>'`. Run
`national-parks <command> --help` to get more information.

```sh
national-parks findParks '{"stateCode":"CA","q":"QUERY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `national-parks findParks` | `{stateCode?: str, q?: str, limit?: number, start?: number, activities?: str}` | Search for national parks based on state, name, activities, or other criteria |

## clinicaltrialsgov-mcp-server

Use `clinicaltrialsgov-mcp-server <command> '<JSON arguments>'`. Run
`clinicaltrialsgov-mcp-server <command> --help` to get more information.

```sh
clinicaltrialsgov-mcp-server clinicaltrials-list-studies '{"query":{"cond":"CONDITION"},"pageSize":10}'
```

| Command | Arguments | Description |
|---|---|---|
| `clinicaltrialsgov-mcp-server clinicaltrials-list-studies` | `{query?: {cond?: str, term?: str, locn?: str, titles?: str, intr?: str, outc?: str, spons?: str, id?: str}, filter?: {ids?: list[str], overallStatus?: list["ACTIVE_NOT_RECRUITING" \| "COMPLETED" \| "ENROLLING_BY_INVITATION" \| "NOT_YET_RECRUITING" \| "RECRUITING" \| "SUSPENDED" \| "TERMINATED" \| "WITHDRAWN" \| "UNKNOWN"], geo?: dict, advanced?: str}, fields?: list[str], sort?: list[str], pageSize?: int = 5, pageToken?: str, countTotal?: bool = true}` | Searches for clinical studies using a combination of query terms and filters. Supports pagination, sorting, and geographic filtering. |

## oxylabs

Use `oxylabs <command> '<JSON arguments>'`. Run `oxylabs <command> --help`
to get more information.

```sh
oxylabs universal-scraper '{"url":"https://example.com","output_format":"md"}'
```

| Command | Arguments | Description |
|---|---|---|
| `oxylabs universal-scraper` | `{url: str, render?: "" \| "html" = "", user_agent_type?: "" \| "desktop" \| "desktop_chrome" \| "desktop_firefox" \| "desktop_safari" \| "desktop_edge" \| "desktop_opera" \| "mobile" \| "mobile_ios" \| "mobile_android" \| "tablet" = "", geo_location?: str = "", output_format?: "" \| "links" \| "md" \| "html" = ""}` | Get a content of any webpage. |

## arxiv

Use `arxiv <command> '<JSON arguments>'`. Run `arxiv <command> --help` to
get more information.

```sh
arxiv search-papers '{"query":"QUERY","max_results":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `arxiv search-papers` | `{query: str, max_results?: int, date_from?: str, date_to?: str, categories?: list[str]}` | Search for papers on arXiv with advanced filtering |
