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
mongodb list-databases '{}'
mongodb collection-schema '{"database":"DATABASE","collection":"COLLECTION"}'
mongodb count '{"database":"DATABASE","collection":"COLLECTION","query":{"FIELD":"VALUE"}}'
mongodb db-stats '{"database":"DATABASE"}'
mongodb aggregate '{"database":"DATABASE","collection":"COLLECTION","pipeline":[{"$group":{"_id":"$FIELD","total":{"$sum":1}}}]}'
```

| Command | Arguments | Description |
|---|---|---|
| `mongodb list-collections` | `{database: str}` | List all collections for a given database |
| `mongodb list-databases` | `{}` | List all databases for a MongoDB connection |
| `mongodb collection-schema` | `{database: str, collection: str}` | Describe the schema for a collection |
| `mongodb count` | `{database: str, collection: str, query?: dict}` | Gets the number of documents in a MongoDB collection using db.collection.count() and query as an optional filter parameter |
| `mongodb db-stats` | `{database: str}` | Returns statistics that reflect the use state of a single database |
| `mongodb aggregate` | `{database: str, collection: str, pipeline: list[dict]}` | Run an aggregation against a MongoDB collection |

## wikipedia

Use `wikipedia <command> '<JSON arguments>'`. Run
`wikipedia <command> --help` to get more information.

```sh
wikipedia get-article '{"title":"TITLE"}'
wikipedia get-summary '{"title":"TITLE"}'
wikipedia summarize-article-for-query '{"title":"TITLE","query":"QUERY"}'
wikipedia summarize-article-section '{"title":"TITLE","section_title":"SECTION"}'
```

| Command | Arguments | Description |
|---|---|---|
| `wikipedia get-article` | `{title: str}` | Get the full content of a Wikipedia article. |
| `wikipedia get-summary` | `{title: str}` | Get a summary of a Wikipedia article. |
| `wikipedia summarize-article-for-query` | `{title: str, query: str, max_length?: int = 250}` | Get a summary of a Wikipedia article tailored to a specific query. |
| `wikipedia summarize-article-section` | `{title: str, section_title: str, max_length?: int = 150}` | Get a summary of a specific section of a Wikipedia article. |
