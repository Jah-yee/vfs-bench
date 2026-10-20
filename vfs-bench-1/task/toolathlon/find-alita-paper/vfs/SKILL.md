---
name: workspace-commands
description: The shell commands and task tools available in this workspace.
---

# Available commands

Python (`python` or `python3`), Perl, JavaScript/Node.js, and TypeScript
runtimes are unavailable. Use the shell commands and task CLIs documented
below; do not probe for or attempt to install other runtimes.

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## arxiv-local

Use `arxiv-local <command> '<JSON arguments>'`. Run
`arxiv-local <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `arxiv-local search-papers` | `{query: str, max_results?: int, date_from?: str, date_to?: str, categories?: list[str]}` | Search for papers on arXiv with advanced filtering |
| `arxiv-local download-paper` | `{paper_id: str, check_status?: bool = false}` | Download a paper and create a resource for it — `paper_id`: The arXiv ID of the paper to download; `check_status`: If true, only check conversion status without downloading |
| `arxiv-local list-papers` | `{}` | List all existing papers available as resources |
| `arxiv-local read-paper` | `{paper_id: str}` | Read the full content of a stored paper in markdown format — `paper_id`: The arXiv ID of the paper to read |

## scholarly

Use `scholarly <command> '<JSON arguments>'`. Run
`scholarly <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `scholarly search-arxiv` | `{keyword: str}` | Search arxiv for articles related to the given keyword. |
| `scholarly search-google-scholar` | `{keyword: str}` | Search google scholar for articles related to the given keyword. |
