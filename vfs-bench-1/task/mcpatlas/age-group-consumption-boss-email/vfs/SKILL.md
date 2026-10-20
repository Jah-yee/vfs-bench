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

You can also use `gh` for GitHub and `git`.

## notion

Use `notion <command> '<JSON arguments>'`. Run `notion <command> --help` to
get more information.

```sh
notion get-user '{"user_id":"ID"}'
notion get-users '{}'
notion get-self '{}'
notion post-database-query '{"database_id":"ID","filter":{"property":"Name","rich_text":{"contains":"TEXT"}},"page_size":10}'
notion post-search '{"query":"QUERY"}'
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
| `notion retrieve-a-block` | `{block_id: str}` | Retrieve a block |
| `notion retrieve-a-page` | `{page_id: str, filter_properties?: str}` | Retrieve a page |
| `notion retrieve-a-database` | `{database_id: str}` | Retrieve a database |

## python3

Execute Python code and return stdout and stderr. Code can be pasted into a
`.py` file and run with `python3`. Python cannot launch subprocesses or make
direct network requests. Run the documented service commands directly in
the shell. Use Python for local file processing and generating JSON
arguments.
