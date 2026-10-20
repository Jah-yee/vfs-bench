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
```

| Command | Arguments | Description |
|---|---|---|
| `notion get-user` | `{user_id: str}` | Retrieve a user Error Responses: 400: 400 |
| `notion get-users` | `{start_cursor?: str, page_size?: int = 100}` | List all users Error Responses: 400: 400 |

## slack

Use `slack <command> '<JSON arguments>'`. Run `slack <command> --help` to
get more information.

```sh
slack channels-list '{"channel_types":"public_channel,private_channel"}'
```

| Command | Arguments | Description |
|---|---|---|
| `slack channels-list` | `{channel_types: str, cursor?: str, limit?: number = 100, sort?: str}` | Get list of channels |
| `slack conversations-add-message` | `{channel_id: str, content_type?: str = "text/markdown", payload?: str, thread_ts?: str}` | Add a message to a public channel, private channel, or direct message (DM, or IM) conversation by channel_id and thread_ts. |

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

## weather-data

Use `weather-data <command> '<JSON arguments>'`. Run
`weather-data <command> --help` to get more information.

```sh
weather-data weather-history '{"q":"CITY","dt":"2025-06-01"}'
weather-data weather-astronomy '{"q":"CITY","dt":"2025-06-01"}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather-data weather-history` | `{q: str, dt: str}` | Get historical weather for a location on a given date (YYYY-MM-DD). Args: q (str): Location query. dt (str): Date in YYYY-MM-DD format. Returns: dict: WeatherAPI history JSON. |
| `weather-data weather-astronomy` | `{q: str, dt: str}` | Get astronomy data (sunrise, sunset, moon) for a date (YYYY-MM-DD). Args: q (str): Location query. dt (str): Date in YYYY-MM-DD format. Returns: dict: WeatherAPI astronomy JSON. |
