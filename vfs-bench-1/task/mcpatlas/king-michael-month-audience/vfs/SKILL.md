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

## wikipedia

Use `wikipedia <command> '<JSON arguments>'`. Run
`wikipedia <command> --help` to get more information.

```sh
wikipedia search-wikipedia '{"query":"QUERY"}'
wikipedia get-article '{"title":"TITLE"}'
```

| Command | Arguments | Description |
|---|---|---|
| `wikipedia search-wikipedia` | `{query: str, limit?: int = 10}` | Search Wikipedia for articles matching a query. |
| `wikipedia get-article` | `{title: str}` | Get the full content of a Wikipedia article. |

## weather

Use `weather <command> '<JSON arguments>'`. Run `weather <command> --help`
to get more information.

```sh
weather get-current-weather '{"location":"40.7128,-74.0060"}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather get-current-weather` | `{location: str}` | Get current weather conditions for a location in the United States. Perfect for 'What's the weather like in [US location]?' questions. Covers all US states, territories, and coastal waters. |

## e2b-server

Use `e2b-server <command> '<JSON arguments>'`. Run
`e2b-server <command> --help` to get more information.

```sh
e2b-server run-code '{"code":"print(1 + 1)"}'
```

| Command | Arguments | Description |
|---|---|---|
| `e2b-server run-code` | `{code: str}` | Run python code in a secure sandbox by E2B. Using the Jupyter Notebook syntax. |

## exa

Use `exa <command> '<JSON arguments>'`. Run `exa <command> --help` to get
more information.

```sh
exa web-search-exa '{"query":"QUERY","numResults":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `exa web-search-exa` | `{query: str, numResults?: number}` | Search the web for any topic and get clean, ready-to-use content. |

## open-library

Use `open-library <command> '<JSON arguments>'`. Run
`open-library <command> --help` to get more information.

```sh
open-library get-book-by-title '{"title":"TITLE"}'
open-library get-authors-by-name '{"name":"NAME"}'
open-library get-author-info '{"author_key":"AUTHOR_KEY"}'
open-library get-author-photo '{"olid":"AUTHOR_OLID"}'
open-library get-book-cover '{"key":"ISBN","value":"ISBN","size":"M"}'
open-library get-book-by-id '{"idType":"isbn","idValue":"ISBN"}'
```

| Command | Arguments | Description |
|---|---|---|
| `open-library get-book-by-title` | `{title: str}` | Search for a book by its title on Open Library. |
| `open-library get-authors-by-name` | `{name: str}` | Search for author information on Open Library. |
| `open-library get-author-info` | `{author_key: str}` | Get detailed information for a specific author using their Open Library Author Key (e.g. OL23919A). |
| `open-library get-author-photo` | `{olid: str}` | Get the URL for an author's photo using their Open Library Author ID (OLID e.g. OL23919A). |
| `open-library get-book-cover` | `{key: "ISBN" \| "OCLC" \| "LCCN" \| "OLID" \| "ID", value: str, size?: "S" \| "M" \| "L"}` | Get the URL for a book's cover image using a key (ISBN, OCLC, LCCN, OLID, ID) and value. |
| `open-library get-book-by-id` | `{idType: "isbn" \| "lccn" \| "oclc" \| "olid", idValue: str}` | Get detailed information about a book using its identifier (ISBN, LCCN, OCLC, OLID). |
