---
name: workspace-commands
description: The shell commands and task tools available in this workspace.
---

# Available commands

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip  curl

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## arxiv-latex

Use `arxiv-latex <command> '<JSON arguments>'`. Run
`arxiv-latex <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `arxiv-latex get-paper-prompt` | `{arxiv_id: str}` | Get a flattened LaTeX code of a paper from arXiv ID. Args: arxiv_id: The arXiv ID of the paper (e.g., '2403.12345') Returns: A flattened LaTeX code of the paper that can be used as a prompt for an LLM |

## git

Use `git --help` for Git operations on workspace repositories.

## python3

Execute Python code directly under the agent workspace and return stdout
and stderr. Code can be pasted into a `.py` file and run with `python3`.

Python cannot launch subprocesses or make direct network requests. Run the
documented service commands directly in the shell. Use Python for local
file processing and generating JSON arguments.
