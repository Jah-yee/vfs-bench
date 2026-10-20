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

## python3

Execute Python code and return stdout and stderr. Code can be pasted into a
`.py` file and run with `python3`. Python cannot launch subprocesses or make
direct network requests. Run the documented service commands directly in
the shell. Use Python for local file processing and generating JSON
arguments.
