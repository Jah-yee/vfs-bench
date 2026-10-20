---
name: workspace-commands
description: Use when running commands in this workspace - which commands exist, what they can do, and what the interpreter supports.
---

# Available commands

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
```

| Command | Arguments | Description |
|---|---|---|
| `slack channels-list` | `{channel_types: str, cursor?: str, limit?: number = 100, sort?: str}` | Get list of channels |
| `slack conversations-add-message` | `{channel_id: str, content_type?: str = "text/markdown", payload?: str, thread_ts?: str}` | Add a message to a public channel, private channel, or direct message (DM, or IM) conversation by channel_id and thread_ts. |
| `slack conversations-history` | `{channel_id: str, cursor?: str, include_activity_messages?: bool = false, limit?: str = "1d"}` | Get messages from the channel (or DM) by channel_id, the last row/column in the response is used as 'cursor' parameter for pagination if not empty |

## airtable

Use `airtable <command> '<JSON arguments>'`. Run `airtable <command> --help`
to get more information.

```sh
airtable list-bases '{}'
airtable list-tables '{"base_id":"BASE_ID"}'
airtable list-records '{"base_id":"BASE_ID","table_name":"TABLE","max_records":10}'
airtable search-records '{"base_id":"BASE_ID","table_name":"TABLE","field_name":"FIELD","value":"VALUE"}'
```

| Command | Arguments | Description |
|---|---|---|
| `airtable list-bases` | `{}` | List all accessible Airtable bases |
| `airtable list-tables` | `{base_id: str}` | List all tables in a base |
| `airtable list-records` | `{base_id: str, table_name: str, max_records?: number}` | List records in a table |
| `airtable search-records` | `{base_id: str, table_name: str, field_name: str, value: str}` | Search for records in a table |

## exa

Use `exa <command> '<JSON arguments>'`. Run `exa <command> --help` to get
more information.

```sh
exa web-search-exa '{"query":"QUERY","numResults":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `exa web-search-exa` | `{query: str, numResults?: number}` | Search the web for any topic and get clean, ready-to-use content. |

## python3

Execute Python code and return stdout and stderr. Code can be pasted into a
`.py` file and run with `python3`. Python cannot launch subprocesses or make
direct network requests. Run the documented service commands directly in
the shell. Use Python for local file processing and generating JSON
arguments.
