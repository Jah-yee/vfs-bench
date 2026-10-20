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

## airtable

Use `airtable <command> '<JSON arguments>'`. Run `airtable <command> --help`
to get more information.

```sh
airtable list-bases '{}'
airtable list-tables '{"base_id":"BASE_ID"}'
airtable list-records '{"base_id":"BASE_ID","table_name":"TABLE","max_records":10}'
airtable search-records '{"base_id":"BASE_ID","table_name":"TABLE","field_name":"FIELD","value":"VALUE"}'
airtable get-record '{"base_id":"BASE_ID","table_name":"TABLE","record_id":"RECORD_ID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `airtable list-bases` | `{}` | List all accessible Airtable bases |
| `airtable list-tables` | `{base_id: str}` | List all tables in a base |
| `airtable list-records` | `{base_id: str, table_name: str, max_records?: number}` | List records in a table |
| `airtable search-records` | `{base_id: str, table_name: str, field_name: str, value: str}` | Search for records in a table |
| `airtable get-record` | `{base_id: str, table_name: str, record_id: str}` | Get a single record by its ID |

## arxiv

Use `arxiv <command> '<JSON arguments>'`. Run `arxiv <command> --help` to
get more information.

```sh
arxiv search-papers '{"query":"QUERY","max_results":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `arxiv search-papers` | `{query: str, max_results?: int, date_from?: str, date_to?: str, categories?: list[str]}` | Search for papers on arXiv with advanced filtering |

## oxylabs

Use `oxylabs <command> '<JSON arguments>'`. Run `oxylabs <command> --help`
to get more information.

```sh
oxylabs universal-scraper '{"url":"https://example.com","output_format":"md"}'
oxylabs google-search-scraper '{"query":"QUERY"}'
oxylabs amazon-search-scraper '{"query":"QUERY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `oxylabs universal-scraper` | `{url: str, render?: "" \| "html" = "", user_agent_type?: "" \| "desktop" \| "desktop_chrome" \| "desktop_firefox" \| "desktop_safari" \| "desktop_edge" \| "desktop_opera" \| "mobile" \| "mobile_ios" \| "mobile_android" \| "tablet" = "", geo_location?: str = "", output_format?: "" \| "links" \| "md" \| "html" = ""}` | Get a content of any webpage. |
| `oxylabs google-search-scraper` | `{query: str, parse?: bool = true, render?: "" \| "html" = "", user_agent_type?: "" \| "desktop" \| "desktop_chrome" \| "desktop_firefox" \| "desktop_safari" \| "desktop_edge" \| "desktop_opera" \| "mobile" \| "mobile_ios" \| "mobile_android" \| "tablet" = "", start_page?: int = 0, pages?: int = 0, limit?: int = 0, domain?: str = "", geo_location?: str = "", locale?: str = "", ad_mode?: bool = false, output_format?: "" \| "links" \| "md" \| "html" = ""}` | Scrape Google Search results. |
| `oxylabs amazon-search-scraper` | `{query: str, category_id?: str = "", merchant_id?: str = "", currency?: str = "", parse?: bool = true, render?: "" \| "html" = "", user_agent_type?: "" \| "desktop" \| "desktop_chrome" \| "desktop_firefox" \| "desktop_safari" \| "desktop_edge" \| "desktop_opera" \| "mobile" \| "mobile_ios" \| "mobile_android" \| "tablet" = "", start_page?: int = 0, pages?: int = 0, domain?: str = "", geo_location?: str = "", locale?: str = "", output_format?: "" \| "links" \| "md" \| "html" = ""}` | Scrape Amazon search results. |

## national-parks

Use `national-parks <command> '<JSON arguments>'`. Run
`national-parks <command> --help` to get more information.

```sh
national-parks findParks '{"stateCode":"CA","q":"QUERY"}'
national-parks getParkDetails '{"parkCode":"PARK_CODE"}'
```

| Command | Arguments | Description |
|---|---|---|
| `national-parks findParks` | `{stateCode?: str, q?: str, limit?: number, start?: number, activities?: str}` | Search for national parks based on state, name, activities, or other criteria |
| `national-parks getParkDetails` | `{parkCode: str}` | Get detailed information about a specific national park |

## memory

Use `memory <command> '<JSON arguments>'`. Run `memory <command> --help` to
get more information.

```sh
memory read-graph '{}'
memory search-nodes '{"query":"QUERY"}'
memory open-nodes '{"names":["NAME"]}'
```

| Command | Arguments | Description |
|---|---|---|
| `memory read-graph` | `{}` | Read the entire knowledge graph |
| `memory search-nodes` | `{query: str}` | Search for nodes in the knowledge graph based on a query |
| `memory open-nodes` | `{names: list[str]}` | Open specific nodes in the knowledge graph by their names |

## fetch

Use `fetch <command> '<JSON arguments>'`. Run `fetch <command> --help` to
get more information.

```sh
fetch fetch '{"url":"https://example.com"}'
```

| Command | Arguments | Description |
|---|---|---|
| `fetch fetch` | `{url: str, max_length?: int = 5000, start_index?: int = 0, raw?: bool = false}` | Fetches a URL from the internet and optionally extracts its contents as markdown. |
