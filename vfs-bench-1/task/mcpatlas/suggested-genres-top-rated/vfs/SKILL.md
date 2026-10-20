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

You can also use `gh` for GitHub.

## slack

Use `slack <command> '<JSON arguments>'`. Run `slack <command> --help` to
get more information.

```sh
slack channels-list '{"channel_types":"public_channel,private_channel"}'
slack conversations-history '{"channel_id":"CHANNEL_ID","limit":"1d"}'
slack conversations-search-messages '{"search_query":"QUERY","filter_in_channel":"CHANNEL_ID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `slack channels-list` | `{channel_types: str, cursor?: str, limit?: number = 100, sort?: str}` | Get list of channels |
| `slack conversations-history` | `{channel_id: str, cursor?: str, include_activity_messages?: bool = false, limit?: str = "1d"}` | Get messages from the channel (or DM) by channel_id, the last row/column in the response is used as 'cursor' parameter for pagination if not empty |
| `slack conversations-search-messages` | `{cursor?: str = "", filter_date_after?: str, filter_date_before?: str, filter_date_during?: str, filter_date_on?: str, filter_in_channel?: str, filter_in_im_or_mpim?: str, filter_threads_only?: bool, filter_users_from?: str, filter_users_with?: str, limit?: number = 20, search_query?: str}` | Search messages in a public channel, private channel, or direct message (DM, or IM) conversation using filters. All filters are optional, if not provided then search_query is required. |

## memory

Use `memory <command> '<JSON arguments>'`. Run `memory <command> --help` to
get more information.

```sh
memory search-nodes '{"query":"QUERY"}'
memory open-nodes '{"names":["NAME"]}'
```

| Command | Arguments | Description |
|---|---|---|
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
