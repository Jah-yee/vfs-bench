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

You can also use `gh` for GitHub and `git`.

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

## google-maps

Use `google-maps <command> '<JSON arguments>'`. Run
`google-maps <command> --help` to get more information.

```sh
google-maps maps-geocode '{"address":"ADDRESS"}'
google-maps maps-search-places '{"query":"QUERY"}'
google-maps maps-place-details '{"place_id":"PLACE_ID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `google-maps maps-geocode` | `{address: str}` | Convert an address into geographic coordinates |
| `google-maps maps-search-places` | `{query: str, location?: {latitude?: number, longitude?: number}, radius?: number}` | Search for places using Google Places API |
| `google-maps maps-place-details` | `{place_id: str}` | Get detailed information about a specific place |

## context7

Use `context7 <command> '<JSON arguments>'`. Run `context7 <command> --help`
to get more information.

```sh
context7 resolve-library-id '{"libraryName":"LIBRARY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `context7 resolve-library-id` | `{libraryName: str}` | Resolves a package/product name to a Context7-compatible library ID and returns a list of matching libraries. |

## weather

Use `weather <command> '<JSON arguments>'`. Run `weather <command> --help`
to get more information.

```sh
weather get-current-weather '{"location":"40.7128,-74.0060"}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather get-current-weather` | `{location: str}` | Get current weather conditions for a location in the United States. Perfect for 'What's the weather like in [US location]?' questions. Covers all US states, territories, and coastal waters. |

## open-library

Use `open-library <command> '<JSON arguments>'`. Run
`open-library <command> --help` to get more information.

```sh
open-library get-book-by-title '{"title":"TITLE"}'
open-library get-authors-by-name '{"name":"NAME"}'
open-library get-author-info '{"author_key":"AUTHOR_KEY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `open-library get-book-by-title` | `{title: str}` | Search for a book by its title on Open Library. |
| `open-library get-authors-by-name` | `{name: str}` | Search for author information on Open Library. |
| `open-library get-author-info` | `{author_key: str}` | Get detailed information for a specific author using their Open Library Author Key (e.g. OL23919A). |

## pubmed

Use `pubmed <command> '<JSON arguments>'`. Run `pubmed <command> --help` to
get more information.

```sh
pubmed search-pubmed-key-words '{"key_words":"QUERY","num_results":5}'
pubmed search-pubmed-advanced '{"term":"QUERY","num_results":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `pubmed search-pubmed-key-words` | `{key_words: str, num_results?: int = 10}` |  |
| `pubmed search-pubmed-advanced` | `{term?: str = null, title?: str = null, author?: str = null, journal?: str = null, start_date?: str = null, end_date?: str = null, num_results?: int = 10}` |  |
