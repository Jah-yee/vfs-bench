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

## slack

Use `slack <command> '<JSON arguments>'`. Run `slack <command> --help` to
get more information.

```sh
slack channels-list '{"channel_types":"public_channel,private_channel"}'
slack conversations-history '{"channel_id":"CHANNEL_ID","limit":"1d"}'
slack conversations-replies '{"channel_id":"CHANNEL_ID","thread_ts":"1234567890.123456"}'
slack conversations-search-messages '{"search_query":"QUERY","filter_in_channel":"CHANNEL_ID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `slack channels-list` | `{channel_types: str, cursor?: str, limit?: number = 100, sort?: str}` | Get list of channels |
| `slack conversations-history` | `{channel_id: str, cursor?: str, include_activity_messages?: bool = false, limit?: str = "1d"}` | Get messages from the channel (or DM) by channel_id, the last row/column in the response is used as 'cursor' parameter for pagination if not empty |
| `slack conversations-replies` | `{channel_id: str, cursor?: str, include_activity_messages?: bool = false, limit?: str = "1d", thread_ts: str}` | Get a thread of messages posted to a conversation by channelID and thread_ts, the last row/column in the response is used as 'cursor' parameter for pagination if not empty |
| `slack conversations-search-messages` | `{cursor?: str = "", filter_date_after?: str, filter_date_before?: str, filter_date_during?: str, filter_date_on?: str, filter_in_channel?: str, filter_in_im_or_mpim?: str, filter_threads_only?: bool, filter_users_from?: str, filter_users_with?: str, limit?: number = 20, search_query?: str}` | Search messages in a public channel, private channel, or direct message (DM, or IM) conversation using filters. All filters are optional, if not provided then search_query is required. |

## memory

Use `memory <command> '<JSON arguments>'`. Run `memory <command> --help` to
get more information.

```sh
memory read-graph '{}'
memory search-nodes '{"query":"QUERY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `memory read-graph` | `{}` | Read the entire knowledge graph |
| `memory search-nodes` | `{query: str}` | Search for nodes in the knowledge graph based on a query |

## fetch

Use `fetch <command> '<JSON arguments>'`. Run `fetch <command> --help` to
get more information.

```sh
fetch fetch '{"url":"https://example.com"}'
```

| Command | Arguments | Description |
|---|---|---|
| `fetch fetch` | `{url: str, max_length?: int = 5000, start_index?: int = 0, raw?: bool = false}` | Fetches a URL from the internet and optionally extracts its contents as markdown. |

## oxylabs

Use `oxylabs <command> '<JSON arguments>'`. Run `oxylabs <command> --help`
to get more information.

```sh
oxylabs universal-scraper '{"url":"https://example.com","output_format":"md"}'
oxylabs amazon-search-scraper '{"query":"QUERY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `oxylabs universal-scraper` | `{url: str, render?: "" \| "html" = "", user_agent_type?: "" \| "desktop" \| "desktop_chrome" \| "desktop_firefox" \| "desktop_safari" \| "desktop_edge" \| "desktop_opera" \| "mobile" \| "mobile_ios" \| "mobile_android" \| "tablet" = "", geo_location?: str = "", output_format?: "" \| "links" \| "md" \| "html" = ""}` | Get a content of any webpage. |
| `oxylabs amazon-search-scraper` | `{query: str, category_id?: str = "", merchant_id?: str = "", currency?: str = "", parse?: bool = true, render?: "" \| "html" = "", user_agent_type?: "" \| "desktop" \| "desktop_chrome" \| "desktop_firefox" \| "desktop_safari" \| "desktop_edge" \| "desktop_opera" \| "mobile" \| "mobile_ios" \| "mobile_android" \| "tablet" = "", start_page?: int = 0, pages?: int = 0, domain?: str = "", geo_location?: str = "", locale?: str = "", output_format?: "" \| "links" \| "md" \| "html" = ""}` | Scrape Amazon search results. |
