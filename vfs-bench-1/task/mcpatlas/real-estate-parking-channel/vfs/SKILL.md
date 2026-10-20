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
memory read-graph '{}'
```

| Command | Arguments | Description |
|---|---|---|
| `memory read-graph` | `{}` | Read the entire knowledge graph |
