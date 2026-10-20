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

## weather

Use `weather <command> '<JSON arguments>'`. Run `weather <command> --help`
to get more information.

```sh
weather get-current-weather '{"location":"40.7128,-74.0060"}'
weather get-weather-forecast '{"location":"40.7128,-74.0060","days":3}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather get-current-weather` | `{location: str}` | Get current weather conditions for a location in the United States. Perfect for 'What's the weather like in [US location]?' questions. Covers all US states, territories, and coastal waters. |
| `weather get-weather-forecast` | `{location: str, days?: number = 7}` | Get multi-day weather forecast for a location in the United States. Perfect for 'What's the forecast for [US location]?' questions. Provides detailed day/night forecasts for up to 7 days. |

## context7

Use `context7 <command> '<JSON arguments>'`. Run `context7 <command> --help`
to get more information.

```sh
context7 resolve-library-id '{"libraryName":"LIBRARY"}'
context7 get-library-docs '{"context7CompatibleLibraryID":"/ORG/PROJECT","topic":"TOPIC"}'
```

| Command | Arguments | Description |
|---|---|---|
| `context7 resolve-library-id` | `{libraryName: str}` | Resolves a package/product name to a Context7-compatible library ID and returns a list of matching libraries. |
| `context7 get-library-docs` | `{context7CompatibleLibraryID: str, topic?: str, tokens?: number}` | Fetches up-to-date documentation for a library. You must call 'resolve-library-id' first to obtain the exact Context7-compatible library ID required to use this tool, UNLESS the user explicitly provides a library ID in the format '/org/project' or '/org/project/version' in their query. |

## met-museum

Use `met-museum <command> '<JSON arguments>'`. Run
`met-museum <command> --help` to get more information.

```sh
met-museum list-departments '{}'
met-museum search-museum-objects '{"q":"QUERY","hasImages":true}'
```

| Command | Arguments | Description |
|---|---|---|
| `met-museum list-departments` | `{}` | List all departments in the Metropolitan Museum of Art (Met Museum) |
| `met-museum search-museum-objects` | `{q: str, hasImages?: bool = false, title?: bool = false, departmentId?: number}` | Search for objects in the Metropolitan Museum of Art (Met Museum). Will return Total objects found, followed by a list of Object Ids.The parameter title should be set to true if you want to search for objects by title.The parameter hasImages is false by default, but can be set to true to return objects without images.If the parameter hasImages is true, the parameter title should be false. |
