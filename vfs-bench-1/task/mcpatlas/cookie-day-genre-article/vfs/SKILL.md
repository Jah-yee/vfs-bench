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

## google-workspace

Use `google-workspace <command> '<JSON arguments>'`. Run
`google-workspace <command> --help` to get more information.

```sh
google-workspace list-events '{"timeMin":"YYYY-MM-DDT00:00:00Z","timeMax":"YYYY-MM-DDT00:00:00Z","maxResults":50}'
```

| Command | Arguments | Description |
|---|---|---|
| `google-workspace list-events` | `{maxResults?: number, timeMin?: str, timeMax?: str}` | List upcoming calendar events |

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

## arxiv

Use `arxiv <command> '<JSON arguments>'`. Run `arxiv <command> --help` to
get more information.

```sh
arxiv search-papers '{"query":"QUERY","max_results":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `arxiv search-papers` | `{query: str, max_results?: int, date_from?: str, date_to?: str, categories?: list[str]}` | Search for papers on arXiv with advanced filtering |
