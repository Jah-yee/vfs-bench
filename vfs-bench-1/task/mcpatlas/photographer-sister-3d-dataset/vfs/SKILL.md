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

## whois

Use `whois <command> '<JSON arguments>'`. Run `whois <command> --help` to
get more information.

```sh
whois whois-domain '{"domain":"example.com"}'
```

| Command | Arguments | Description |
|---|---|---|
| `whois whois-domain` | `{domain: str}` | Looksup whois information about the domain |

## pubmed

Use `pubmed <command> '<JSON arguments>'`. Run `pubmed <command> --help` to
get more information.

```sh
pubmed search-pubmed-key-words '{"key_words":"QUERY","num_results":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `pubmed search-pubmed-key-words` | `{key_words: str, num_results?: int = 10}` |  |

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

## arxiv

Use `arxiv <command> '<JSON arguments>'`. Run `arxiv <command> --help` to
get more information.

```sh
arxiv search-papers '{"query":"QUERY","max_results":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `arxiv search-papers` | `{query: str, max_results?: int, date_from?: str, date_to?: str, categories?: list[str]}` | Search for papers on arXiv with advanced filtering |
