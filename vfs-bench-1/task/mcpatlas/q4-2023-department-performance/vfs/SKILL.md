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

## national-parks

Use `national-parks <command> '<JSON arguments>'`. Run
`national-parks <command> --help` to get more information.

```sh
national-parks findParks '{"stateCode":"CA","q":"QUERY"}'
national-parks getParkDetails '{"parkCode":"PARK_CODE"}'
national-parks getVisitorCenters '{"parkCode":"PARK_CODE"}'
national-parks getCampgrounds '{"parkCode":"PARK_CODE","limit":10}'
```

| Command | Arguments | Description |
|---|---|---|
| `national-parks findParks` | `{stateCode?: str, q?: str, limit?: number, start?: number, activities?: str}` | Search for national parks based on state, name, activities, or other criteria |
| `national-parks getParkDetails` | `{parkCode: str}` | Get detailed information about a specific national park |
| `national-parks getVisitorCenters` | `{parkCode?: str, limit?: number, start?: number, q?: str}` | Get information about visitor centers and their operating hours |
| `national-parks getCampgrounds` | `{parkCode?: str, limit?: number, start?: number, q?: str}` | Get information about available campgrounds and their amenities |

## calculator

Use `calculator <command> '<JSON arguments>'`. Run
`calculator <command> --help` to get more information.

```sh
calculator calculate '{"expression":"2 * (3 + 4)"}'
```

| Command | Arguments | Description |
|---|---|---|
| `calculator calculate` | `{expression: str}` | Calculates/evaluates the given expression. |

## arxiv

Use `arxiv <command> '<JSON arguments>'`. Run `arxiv <command> --help` to
get more information.

```sh
arxiv search-papers '{"query":"QUERY","max_results":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `arxiv search-papers` | `{query: str, max_results?: int, date_from?: str, date_to?: str, categories?: list[str]}` | Search for papers on arXiv with advanced filtering |

## python3

Execute Python code and return stdout and stderr. Code can be pasted into a
`.py` file and run with `python3`. Python cannot launch subprocesses or make
direct network requests. Run the documented service commands directly in
the shell. Use Python for local file processing and generating JSON
arguments.
