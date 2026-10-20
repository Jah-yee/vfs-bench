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

You can also use `git`.

## google-workspace

Use `google-workspace <command> '<JSON arguments>'`. Run
`google-workspace <command> --help` to get more information.

```sh
google-workspace list-events '{"timeMin":"YYYY-MM-DDT00:00:00Z","timeMax":"YYYY-MM-DDT00:00:00Z","maxResults":50}'
```

| Command | Arguments | Description |
|---|---|---|
| `google-workspace list-events` | `{maxResults?: number, timeMin?: str, timeMax?: str}` | List upcoming calendar events |

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

## calculator

Use `calculator <command> '<JSON arguments>'`. Run
`calculator <command> --help` to get more information.

```sh
calculator calculate '{"expression":"2 * (3 + 4)"}'
```

| Command | Arguments | Description |
|---|---|---|
| `calculator calculate` | `{expression: str}` | Calculates/evaluates the given expression. |

## fetch

Use `fetch <command> '<JSON arguments>'`. Run `fetch <command> --help` to
get more information.

```sh
fetch fetch '{"url":"https://example.com"}'
```

| Command | Arguments | Description |
|---|---|---|
| `fetch fetch` | `{url: str, max_length?: int = 5000, start_index?: int = 0, raw?: bool = false}` | Fetches a URL from the internet and optionally extracts its contents as markdown. |

## mcp-server-code-runner

Use `mcp-server-code-runner <command> '<JSON arguments>'`. Run
`mcp-server-code-runner <command> --help` to get more information.

```sh
mcp-server-code-runner run-code '{"code":"print(1 + 1)","languageId":"python"}'
```

| Command | Arguments | Description |
|---|---|---|
| `mcp-server-code-runner run-code` | `{code: str, languageId: "javascript" \| "php" \| "python" \| "perl" \| "perl6" \| "ruby" \| "go" \| "lua" \| "groovy" \| "powershell" \| "bat" \| "shellscript" \| "fsharp" \| "csharp" \| "vbscript" \| "typescript" \| "coffeescript" \| "scala" \| "swift" \| "julia" \| "crystal" \| "ocaml" \| "r" \| "applescript" \| "clojure" \| "racket" \| "scheme" \| "ahk" \| "autoit" \| "dart" \| "haskell" \| "nim" \| "lisp" \| "kit" \| "v" \| "sass" \| "scss"}` | Run code snippet and return the result. |

## national-parks

Use `national-parks <command> '<JSON arguments>'`. Run
`national-parks <command> --help` to get more information.

```sh
national-parks findParks '{"stateCode":"CA","q":"QUERY"}'
national-parks getParkDetails '{"parkCode":"PARK_CODE"}'
national-parks getVisitorCenters '{"parkCode":"PARK_CODE"}'
national-parks getCampgrounds '{"parkCode":"PARK_CODE","limit":10}'
```

| Command | Arguments | Description |
|---|---|---|
| `national-parks findParks` | `{stateCode?: str, q?: str, limit?: number, start?: number, activities?: str}` | Search for national parks based on state, name, activities, or other criteria |
| `national-parks getParkDetails` | `{parkCode: str}` | Get detailed information about a specific national park |
| `national-parks getVisitorCenters` | `{parkCode?: str, limit?: number, start?: number, q?: str}` | Get information about visitor centers and their operating hours |
| `national-parks getCampgrounds` | `{parkCode?: str, limit?: number, start?: number, q?: str}` | Get information about available campgrounds and their amenities |

## exa

Use `exa <command> '<JSON arguments>'`. Run `exa <command> --help` to get
more information.

```sh
exa web-search-exa '{"query":"QUERY","numResults":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `exa web-search-exa` | `{query: str, numResults?: number}` | Search the web for any topic and get clean, ready-to-use content. |
