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

## mongodb

Use `mongodb <command> '<JSON arguments>'`. Run `mongodb <command> --help`
to get more information.

```sh
mongodb list-collections '{"database":"DATABASE"}'
mongodb list-databases '{}'
mongodb collection-indexes '{"database":"DATABASE","collection":"COLLECTION"}'
mongodb collection-schema '{"database":"DATABASE","collection":"COLLECTION"}'
mongodb find '{"database":"DATABASE","collection":"COLLECTION","filter":{"FIELD":"VALUE"},"limit":10}'
mongodb count '{"database":"DATABASE","collection":"COLLECTION","query":{"FIELD":"VALUE"}}'
mongodb db-stats '{"database":"DATABASE"}'
mongodb aggregate '{"database":"DATABASE","collection":"COLLECTION","pipeline":[{"$group":{"_id":"$FIELD","total":{"$sum":1}}}]}'
```

| Command | Arguments | Description |
|---|---|---|
| `mongodb list-collections` | `{database: str}` | List all collections for a given database |
| `mongodb list-databases` | `{}` | List all databases for a MongoDB connection |
| `mongodb collection-indexes` | `{database: str, collection: str}` | Describe the indexes for a collection |
| `mongodb collection-schema` | `{database: str, collection: str}` | Describe the schema for a collection |
| `mongodb find` | `{database: str, collection: str, filter?: dict, projection?: dict, limit?: number = 10, sort?: dict}` | Run a find query against a MongoDB collection |
| `mongodb count` | `{database: str, collection: str, query?: dict}` | Gets the number of documents in a MongoDB collection using db.collection.count() and query as an optional filter parameter |
| `mongodb db-stats` | `{database: str}` | Returns statistics that reflect the use state of a single database |
| `mongodb aggregate` | `{database: str, collection: str, pipeline: list[dict]}` | Run an aggregation against a MongoDB collection |

## wikipedia

Use `wikipedia <command> '<JSON arguments>'`. Run
`wikipedia <command> --help` to get more information.

```sh
wikipedia get-article '{"title":"TITLE"}'
```

| Command | Arguments | Description |
|---|---|---|
| `wikipedia get-article` | `{title: str}` | Get the full content of a Wikipedia article. |

## pubmed

Use `pubmed <command> '<JSON arguments>'`. Run `pubmed <command> --help` to
get more information.

```sh
pubmed search-pubmed-key-words '{"key_words":"QUERY","num_results":5}'
pubmed search-pubmed-advanced '{"term":"QUERY","num_results":5}'
pubmed download-pubmed-pdf '{"pmid":"PMID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `pubmed search-pubmed-key-words` | `{key_words: str, num_results?: int = 10}` |  |
| `pubmed search-pubmed-advanced` | `{term?: str = null, title?: str = null, author?: str = null, journal?: str = null, start_date?: str = null, end_date?: str = null, num_results?: int = 10}` |  |
| `pubmed download-pubmed-pdf` | `{pmid: str \| int}` |  |

## weather-data

Use `weather-data <command> '<JSON arguments>'`. Run
`weather-data <command> --help` to get more information.

```sh
weather-data weather-history '{"q":"CITY","dt":"2025-06-01"}'
weather-data weather-astronomy '{"q":"CITY","dt":"2025-06-01"}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather-data weather-history` | `{q: str, dt: str}` | Get historical weather for a location on a given date (YYYY-MM-DD). Args: q (str): Location query. dt (str): Date in YYYY-MM-DD format. Returns: dict: WeatherAPI history JSON. |
| `weather-data weather-astronomy` | `{q: str, dt: str}` | Get astronomy data (sunrise, sunset, moon) for a date (YYYY-MM-DD). Args: q (str): Location query. dt (str): Date in YYYY-MM-DD format. Returns: dict: WeatherAPI astronomy JSON. |
