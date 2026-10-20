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
notion get-user '{"user_id":"ID"}'
notion get-users '{}'
notion get-self '{}'
notion post-database-query '{"database_id":"ID","filter":{"property":"Name","rich_text":{"contains":"TEXT"}},"page_size":10}'
notion post-search '{"query":"QUERY"}'
notion get-block-children '{"block_id":"ID"}'
notion retrieve-a-block '{"block_id":"ID"}'
notion retrieve-a-page '{"page_id":"ID"}'
notion retrieve-a-database '{"database_id":"ID"}'
notion retrieve-a-page-property '{"page_id":"ID","property_id":"PROPERTY_ID"}'
notion retrieve-a-comment '{"block_id":"ID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `notion get-user` | `{user_id: str}` | Retrieve a user Error Responses: 400: 400 |
| `notion get-users` | `{start_cursor?: str, page_size?: int = 100}` | List all users Error Responses: 400: 400 |
| `notion get-self` | `{}` | Retrieve your token's bot user |
| `notion post-database-query` | `{database_id: str, filter_properties?: list[str], filter?: dict, sorts?: list[{property: str, direction: "ascending" \| "descending"}], start_cursor?: str, page_size?: int = 100, archived?: bool, in_trash?: bool}` | Query a database |
| `notion post-search` | `{query?: str, sort?: {direction?: str, timestamp?: str}, filter?: {value?: str, property?: str}, start_cursor?: str, page_size?: int = 100}` | Search by title |
| `notion get-block-children` | `{block_id: str, start_cursor?: str, page_size?: int = 100}` | Retrieve block children |
| `notion retrieve-a-block` | `{block_id: str}` | Retrieve a block |
| `notion retrieve-a-page` | `{page_id: str, filter_properties?: str}` | Retrieve a page |
| `notion retrieve-a-database` | `{database_id: str}` | Retrieve a database |
| `notion retrieve-a-page-property` | `{page_id: str, property_id: str, page_size?: int, start_cursor?: str}` | Retrieve a page property item |
| `notion retrieve-a-comment` | `{block_id: str, start_cursor?: str, page_size?: int}` | Retrieve comments |

## google-workspace

Use `google-workspace <command> '<JSON arguments>'`. Run
`google-workspace <command> --help` to get more information.

```sh
google-workspace list-events '{"timeMin":"YYYY-MM-DDT00:00:00Z","timeMax":"YYYY-MM-DDT00:00:00Z","maxResults":50}'
```

| Command | Arguments | Description |
|---|---|---|
| `google-workspace list-events` | `{maxResults?: number, timeMin?: str, timeMax?: str}` | List upcoming calendar events |

## oxylabs

Use `oxylabs <command> '<JSON arguments>'`. Run `oxylabs <command> --help`
to get more information.

```sh
oxylabs universal-scraper '{"url":"https://example.com","output_format":"md"}'
oxylabs google-search-scraper '{"query":"QUERY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `oxylabs universal-scraper` | `{url: str, render?: "" \| "html" = "", user_agent_type?: "" \| "desktop" \| "desktop_chrome" \| "desktop_firefox" \| "desktop_safari" \| "desktop_edge" \| "desktop_opera" \| "mobile" \| "mobile_ios" \| "mobile_android" \| "tablet" = "", geo_location?: str = "", output_format?: "" \| "links" \| "md" \| "html" = ""}` | Get a content of any webpage. |
| `oxylabs google-search-scraper` | `{query: str, parse?: bool = true, render?: "" \| "html" = "", user_agent_type?: "" \| "desktop" \| "desktop_chrome" \| "desktop_firefox" \| "desktop_safari" \| "desktop_edge" \| "desktop_opera" \| "mobile" \| "mobile_ios" \| "mobile_android" \| "tablet" = "", start_page?: int = 0, pages?: int = 0, limit?: int = 0, domain?: str = "", geo_location?: str = "", locale?: str = "", ad_mode?: bool = false, output_format?: "" \| "links" \| "md" \| "html" = ""}` | Scrape Google Search results. |

## calculator

Use `calculator <command> '<JSON arguments>'`. Run
`calculator <command> --help` to get more information.

```sh
calculator calculate '{"expression":"2 * (3 + 4)"}'
```

| Command | Arguments | Description |
|---|---|---|
| `calculator calculate` | `{expression: str}` | Calculates/evaluates the given expression. |
