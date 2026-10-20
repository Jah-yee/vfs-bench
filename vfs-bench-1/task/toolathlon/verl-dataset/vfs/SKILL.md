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

## web-search

Use `web-search <command> '<JSON arguments>'`. Run
`web-search <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `web-search web-search` | `{query: str, num_results?: int = 10}` | Search the web using Google Serper API with concurrency control and retry mechanisms. Supports various Google search operators. — `query`: Search query with optional Google search operators.; `num_results`: Number of results to return, default 10, max 50 |

## fetch

Use `fetch <command> '<JSON arguments>'`. Run `fetch <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `fetch html` | `{url: str, headers?: dict}` | Fetch a website and return the content as HTML — `url`: URL of the website to fetch; `headers`: Optional headers to include in the request |
| `fetch markdown` | `{url: str, headers?: dict}` | Fetch a website and return the content as Markdown — `url`: URL of the website to fetch; `headers`: Optional headers to include in the request |
| `fetch txt` | `{url: str, headers?: dict}` | Fetch a website, return the content as plain text (no HTML) — `url`: URL of the website to fetch; `headers`: Optional headers to include in the request |
| `fetch json` | `{url: str, headers?: dict}` | Fetch a JSON file from a URL — `url`: URL of the JSON to fetch; `headers`: Optional headers to include in the request |

## huggingface

Use `huggingface <command> '<JSON arguments>'`. Run
`huggingface <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `huggingface hf-whoami` | `{}` | Inspect the current Hugging Face authentication context, including the account, visible organization memberships, and credential access details. Read-only and never returns credential values. |
| `huggingface hub-repo-search` | `{query?: str, repo_types?: list["model" \| "dataset" \| "space"] = ["model", "dataset"], author?: str, filters?: list[str], sort?: "trendingScore" \| "downloads" \| "likes" \| "createdAt" \| "lastModified", limit?: number = 20}` | Search Hugging Face repositories with a shared query interface. You can target models, datasets, spaces, or aggregate across multiple repo types in one call. Include links to repositories in your response. — `query`: Search term. Leave blank and specify sort + limit to browse trending or recent repositories.; `repo_types`: Repository types to search. Defaults to ["model", "dataset"]. space uses keyword search via /api/spaces.; `author`: Organization or user namespace to filter by (e.g. 'google', 'meta-llama', 'huggingface').; `filters`: Optional hub filter tags. Applied to each selected repo type (e.g. ["text-generation"], ["language:en"], ["mcp-server"]).; `sort`: Sort order (descending): trendingScore, downloads, likes, createdAt, lastModified; `limit`: Maximum number of results to return per selected repo type |
| `huggingface hub-repo-details` | `{repo_ids: list[str], repo_type?: "model" \| "dataset" \| "space", operations?: list["overview" \| "dataset_structure" \| "dataset_preview"], config?: str, split?: str, offset?: int, limit?: int}` | Get details for one or more Hugging Face repos (model, dataset, or space). Auto-detects type unless specified. For datasets, use operations: overview, dataset_structure, dataset_preview. Use dataset_structure first to discover configs, splits, sizes, and schema. Use dataset_preview only when config and split are known, unless the dataset has a single config/split. — `repo_ids`: Repo IDs for (models\|dataset/space) - usually in author/name format (e.g. openai/gpt-oss-120b); `repo_type`: Specify lookup type; otherwise auto-detects; `operations`: Details to return. Defaults to ["overview"]. For datasets, prefer ["overview", "dataset_structure"] first; then call ["dataset_preview"] with config and split.; `config`: Dataset Viewer config. Required for dataset_preview when the dataset has multiple config/split options. Discover via dataset_structure.; `split`: Dataset Viewer split. Required for dataset_preview when the dataset has multiple config/split options. Discover via dataset_structure.; `offset`: Row offset for dataset_preview. Defaults to 0.; `limit`: Row count for dataset_preview. Defaults to 5 and is clamped to 1-100. |
| `huggingface hf-fs` | `{operations: list[{cmd: "ls" \| "cat" \| "attach" \| "stat" \| "find" \| "search", args: list[str]}]}` | When to use: Hugging Face Hub models, datasets, Spaces, collections, papers, daily papers, today's trending models, current paper leaderboard, docs, and repository files. Examples: {"operations":[{"cmd":"ls","args":["hf://models/trending","--limit","10"]}]} {"operations":[{"cmd":"ls","args":["hf://papers/trending"]}]} {"operations":[{"cmd":"ls","args":["hf://papers/daily/latest"]}]} Use hf_fs for Hugging Face Hub filesystem operations. Call it with operations, an array of {cmd, args} items; multiple operations may be submitted together. Usage: {"operations":[{"cmd":"ls","args":["hf://models/org/repo"]}]} Grammar; each string below is one args array item: ls URI [--recursive] [--glob GLOB] [--type TYPE] [--sort SORT] [--limit N] cat URI [--offset N] [--max-bytes N] attach URI [--max-bytes N] stat URI find URI [--name GLOB] [--path GLOB] [--type TYPE] [--limit N] search URI [QUERY] [--type TYPE] [--sort SORT] [--tag TAG] [--kind mcp] [--limit N] COMMAND = ls\|cat\|attach\|stat\|find\|search. TYPE = file\|dir\|repo\|bucket\|collection\|paper\|link. SORT = createdAt\|downloads\|likes\|lastModified\|likes30d\|trendingScore\|mainSize\|id\|trending\|upvotes. URI is a canonical hf:// URI. QUERY and GLOB are each one string. Use search for discovery, ls for a known directory, find for recursive matching within a known scope, stat for filesystem metadata or an uncertain target type, cat for text contents, and attach for a complete JPEG, PNG, or WebP image. When the request gives an exact text-file URI, use cat directly; do not add ls or stat first. stat does not read the contents of JSON, Markdown, or other text files. Search scopes: hf://models\|datasets\|spaces[/OWNER], hf://collections[/OWNER], hf://papers, and hf://docs[/...]. Paper and documentation search require QUERY. Repeat --tag only for search hf://spaces; --kind mcp selects MCP Spaces. Use ls hf://models/trending, hf://datasets/trending, hf://spaces/trending, or hf://papers/trending for trending listings. For a named paper.md or metadata.json, use cat directly. Use ls on a paper only to discover an unnamed related VFS. Omit --limit, --sort, and --type unless the request requires them. Limits and path-specific behavior are documented at hf://README.md. Issue one hf_fs call. — `operations.cmd`: Command to execute.; `operations.args`: Command arguments. First item must be an hf:// URI, not a local path or bare filename. One argument per array item. |

## hf

Use `hf --help` for Hugging Face repository, download and upload commands. Repository paths and revisions identify the same files as upstream. Use `huggingface` for the upstream MCP search and Dataset Viewer operations.

## python3

Execute Python code directly under the agent workspace and return stdout
and stderr. Code can be pasted into a `.py` file and run with `python3`.

Python cannot launch subprocesses or make direct network requests. Run the
documented service commands directly in the shell. Use Python for local
file processing and generating JSON arguments.
