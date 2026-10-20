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

## wikipedia

Use `wikipedia <command> '<JSON arguments>'`. Run
`wikipedia <command> --help` to get more information.

```sh
wikipedia search-wikipedia '{"query":"QUERY"}'
wikipedia get-article '{"title":"TITLE"}'
wikipedia get-summary '{"title":"TITLE"}'
wikipedia summarize-article-for-query '{"title":"TITLE","query":"QUERY"}'
wikipedia summarize-article-section '{"title":"TITLE","section_title":"SECTION"}'
wikipedia extract-key-facts '{"title":"TITLE","count":5}'
wikipedia get-related-topics '{"title":"TITLE","limit":10}'
```

| Command | Arguments | Description |
|---|---|---|
| `wikipedia search-wikipedia` | `{query: str, limit?: int = 10}` | Search Wikipedia for articles matching a query. |
| `wikipedia get-article` | `{title: str}` | Get the full content of a Wikipedia article. |
| `wikipedia get-summary` | `{title: str}` | Get a summary of a Wikipedia article. |
| `wikipedia summarize-article-for-query` | `{title: str, query: str, max_length?: int = 250}` | Get a summary of a Wikipedia article tailored to a specific query. |
| `wikipedia summarize-article-section` | `{title: str, section_title: str, max_length?: int = 150}` | Get a summary of a specific section of a Wikipedia article. |
| `wikipedia extract-key-facts` | `{title: str, topic_within_article?: str = "", count?: int = 5}` | Extract key facts from a Wikipedia article, optionally focused on a topic. |
| `wikipedia get-related-topics` | `{title: str, limit?: int = 10}` | Get topics related to a Wikipedia article based on links and categories. |
