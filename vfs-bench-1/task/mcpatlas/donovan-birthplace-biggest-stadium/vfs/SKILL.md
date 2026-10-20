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

## mongodb

Use `mongodb <command> '<JSON arguments>'`. Run `mongodb <command> --help`
to get more information.

```sh
mongodb list-collections '{"database":"DATABASE"}'
```

| Command | Arguments | Description |
|---|---|---|
| `mongodb list-collections` | `{database: str}` | List all collections for a given database |

## airtable

Use `airtable <command> '<JSON arguments>'`. Run `airtable <command> --help`
to get more information.

```sh
airtable get-record '{"base_id":"BASE_ID","table_name":"TABLE","record_id":"RECORD_ID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `airtable get-record` | `{base_id: str, table_name: str, record_id: str}` | Get a single record by its ID |

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

## e2b-server

Use `e2b-server <command> '<JSON arguments>'`. Run
`e2b-server <command> --help` to get more information.

```sh
e2b-server run-code '{"code":"print(1 + 1)"}'
```

| Command | Arguments | Description |
|---|---|---|
| `e2b-server run-code` | `{code: str}` | Run python code in a secure sandbox by E2B. Using the Jupyter Notebook syntax. |

## pubmed

Use `pubmed <command> '<JSON arguments>'`. Run `pubmed <command> --help` to
get more information.

```sh
pubmed search-pubmed-key-words '{"key_words":"QUERY","num_results":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `pubmed search-pubmed-key-words` | `{key_words: str, num_results?: int = 10}` |  |

## clinicaltrialsgov-mcp-server

Use `clinicaltrialsgov-mcp-server <command> '<JSON arguments>'`. Run
`clinicaltrialsgov-mcp-server <command> --help` to get more information.

```sh
clinicaltrialsgov-mcp-server clinicaltrials-get-study '{"nctIds":"NCT00000000","summaryOnly":true}'
```

| Command | Arguments | Description |
|---|---|---|
| `clinicaltrialsgov-mcp-server clinicaltrials-get-study` | `{nctIds: str \| list[str], markupFormat?: "markdown" \| "legacy" = "markdown", fields?: list[str], summaryOnly?: bool = false}` | Fetches one or more clinical studies from ClinicalTrials.gov by their NCT IDs. Returns either complete study data or concise summaries for each. |

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

## osm-mcp-server

Use `osm-mcp-server <command> '<JSON arguments>'`. Run
`osm-mcp-server <command> --help` to get more information.

```sh
osm-mcp-server geocode-address '{"address":"ADDRESS"}'
osm-mcp-server reverse-geocode '{"latitude":LATITUDE,"longitude":LONGITUDE}'
osm-mcp-server find-nearby-places '{"latitude":LATITUDE,"longitude":LONGITUDE,"radius":1000,"limit":20}'
osm-mcp-server find-ev-charging-stations '{"latitude":LATITUDE,"longitude":LONGITUDE,"radius":5000}'
```

| Command | Arguments | Description |
|---|---|---|
| `osm-mcp-server geocode-address` | `{address: str}` | Convert an address or place name to geographic coordinates with detailed location information. |
| `osm-mcp-server reverse-geocode` | `{latitude: number, longitude: number}` | Convert geographic coordinates to a detailed address and location description. |
| `osm-mcp-server find-nearby-places` | `{latitude: number, longitude: number, radius?: number = 1000, categories?: list[str] = null, limit?: int = 20}` | Discover points of interest and amenities near a specific location. |
| `osm-mcp-server find-ev-charging-stations` | `{latitude: number, longitude: number, radius?: number = 5000, connector_types?: list[str] = null, min_power?: number = null}` | Locate electric vehicle charging stations near a specific location. |

## exa

Use `exa <command> '<JSON arguments>'`. Run `exa <command> --help` to get
more information.

```sh
exa web-search-exa '{"query":"QUERY","numResults":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `exa web-search-exa` | `{query: str, numResults?: number}` | Search the web for any topic and get clean, ready-to-use content. |
