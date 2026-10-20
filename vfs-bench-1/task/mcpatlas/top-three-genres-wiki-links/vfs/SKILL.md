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

## mongodb

Use `mongodb <command> '<JSON arguments>'`. Run `mongodb <command> --help`
to get more information.

```sh
mongodb list-collections '{"database":"DATABASE"}'
mongodb list-databases '{}'
mongodb collection-indexes '{"database":"DATABASE","collection":"COLLECTION"}'
mongodb collection-schema '{"database":"DATABASE","collection":"COLLECTION"}'
mongodb find '{"database":"DATABASE","collection":"COLLECTION","filter":{"FIELD":"VALUE"},"limit":10}'
mongodb collection-storage-size '{"database":"DATABASE","collection":"COLLECTION"}'
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
| `mongodb collection-storage-size` | `{database: str, collection: str}` | Gets the size of the collection |
| `mongodb count` | `{database: str, collection: str, query?: dict}` | Gets the number of documents in a MongoDB collection using db.collection.count() and query as an optional filter parameter |
| `mongodb db-stats` | `{database: str}` | Returns statistics that reflect the use state of a single database |
| `mongodb aggregate` | `{database: str, collection: str, pipeline: list[dict]}` | Run an aggregation against a MongoDB collection |

## exa

Use `exa <command> '<JSON arguments>'`. Run `exa <command> --help` to get
more information.

```sh
exa web-search-exa '{"query":"QUERY","numResults":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `exa web-search-exa` | `{query: str, numResults?: number}` | Search the web for any topic and get clean, ready-to-use content. |

## e2b-server

Use `e2b-server <command> '<JSON arguments>'`. Run
`e2b-server <command> --help` to get more information.

```sh
e2b-server run-code '{"code":"print(1 + 1)"}'
```

| Command | Arguments | Description |
|---|---|---|
| `e2b-server run-code` | `{code: str}` | Run python code in a secure sandbox by E2B. Using the Jupyter Notebook syntax. |

## national-parks

Use `national-parks <command> '<JSON arguments>'`. Run
`national-parks <command> --help` to get more information.

```sh
national-parks findParks '{"stateCode":"CA","q":"QUERY"}'
national-parks getParkDetails '{"parkCode":"PARK_CODE"}'
national-parks getVisitorCenters '{"parkCode":"PARK_CODE"}'
```

| Command | Arguments | Description |
|---|---|---|
| `national-parks findParks` | `{stateCode?: str, q?: str, limit?: number, start?: number, activities?: str}` | Search for national parks based on state, name, activities, or other criteria |
| `national-parks getParkDetails` | `{parkCode: str}` | Get detailed information about a specific national park |
| `national-parks getVisitorCenters` | `{parkCode?: str, limit?: number, start?: number, q?: str}` | Get information about visitor centers and their operating hours |
