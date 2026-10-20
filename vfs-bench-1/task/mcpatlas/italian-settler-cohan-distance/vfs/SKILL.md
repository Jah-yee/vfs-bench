---
name: workspace-commands
description: Use when running commands in this workspace - which commands exist, what they can do, and what the interpreter supports.
---

# Available commands

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq

with pipes, `>` redirection and `$(...)` substitution.

Do not probe the machine with `which`, `type`, `--version`, `env`, `ps`,
`echo $PATH`, `ls /usr/bin` or `cat /usr/bin/<command>`: they tell you
nothing about the task.

A filename with a space in it needs quoting, as it would in any shell.

You can also use `gh` for GitHub and `git`.

## ddg-search

Use `ddg-search <command> '<JSON arguments>'`. Run
`ddg-search <command> --help` to get more information.

```sh
ddg-search search '{"query":"QUERY","max_results":5}'
ddg-search fetch-content '{"url":"https://example.com"}'
```

| Command | Arguments | Description |
|---|---|---|
| `ddg-search search` | `{query: str, max_results?: int = 10, region?: str = ""}` | Search the web using DuckDuckGo. Returns a list of results with titles, URLs, and snippets. Use this to find current information, research topics, or locate specific websites. For best results, use specific and descriptive search queries. |
| `ddg-search fetch-content` | `{url: str, start_index?: int = 0, max_length?: int = 8000, backend?: str = null}` | Fetch and extract the main text content from a webpage. Strips out navigation, headers, footers, scripts, and styles to return clean readable text. Use this after searching to read the full content of a specific result. Supports pagination for long pages via start_index and max_length. |

## google-maps

Use `google-maps <command> '<JSON arguments>'`. Run
`google-maps <command> --help` to get more information.

```sh
google-maps maps-search-places '{"query":"QUERY"}'
google-maps maps-place-details '{"place_id":"PLACE_ID"}'
google-maps maps-distance-matrix '{"origins":["ORIGIN"],"destinations":["DESTINATION"],"mode":"driving"}'
google-maps maps-elevation '{"locations":[{"latitude":LATITUDE,"longitude":LONGITUDE}]}'
google-maps maps-directions '{"origin":"ORIGIN","destination":"DESTINATION","mode":"driving"}'
```

| Command | Arguments | Description |
|---|---|---|
| `google-maps maps-search-places` | `{query: str, location?: {latitude?: number, longitude?: number}, radius?: number}` | Search for places using Google Places API |
| `google-maps maps-place-details` | `{place_id: str}` | Get detailed information about a specific place |
| `google-maps maps-distance-matrix` | `{origins: list[str], destinations: list[str], mode?: "driving" \| "walking" \| "bicycling" \| "transit"}` | Calculate travel distance and time for multiple origins and destinations |
| `google-maps maps-elevation` | `{locations: list[{latitude: number, longitude: number}]}` | Get elevation data for locations on the earth |
| `google-maps maps-directions` | `{origin: str, destination: str, mode?: "driving" \| "walking" \| "bicycling" \| "transit"}` | Get directions between two points |

## python3

Execute Python code and return stdout and stderr. Code can be pasted into a
`.py` file and run with `python3`. Python cannot launch subprocesses or make
direct network requests. Run the documented service commands directly in
the shell. Use Python for local file processing and generating JSON
arguments.
