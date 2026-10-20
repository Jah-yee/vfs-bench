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

## e2b-server

Use `e2b-server <command> '<JSON arguments>'`. Run
`e2b-server <command> --help` to get more information.

```sh
e2b-server run-code '{"code":"print(1 + 1)"}'
```

| Command | Arguments | Description |
|---|---|---|
| `e2b-server run-code` | `{code: str}` | Run python code in a secure sandbox by E2B. Using the Jupyter Notebook syntax. |

## fetch

Use `fetch <command> '<JSON arguments>'`. Run `fetch <command> --help` to
get more information.

```sh
fetch fetch '{"url":"https://example.com"}'
```

| Command | Arguments | Description |
|---|---|---|
| `fetch fetch` | `{url: str, max_length?: int = 5000, start_index?: int = 0, raw?: bool = false}` | Fetches a URL from the internet and optionally extracts its contents as markdown. |

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
