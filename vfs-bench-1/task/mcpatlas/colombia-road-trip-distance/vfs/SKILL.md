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

## wikipedia

Use `wikipedia <command> '<JSON arguments>'`. Run
`wikipedia <command> --help` to get more information.

```sh
wikipedia search-wikipedia '{"query":"QUERY"}'
wikipedia get-article '{"title":"TITLE"}'
wikipedia extract-key-facts '{"title":"TITLE","count":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `wikipedia search-wikipedia` | `{query: str, limit?: int = 10}` | Search Wikipedia for articles matching a query. |
| `wikipedia get-article` | `{title: str}` | Get the full content of a Wikipedia article. |
| `wikipedia extract-key-facts` | `{title: str, topic_within_article?: str = "", count?: int = 5}` | Extract key facts from a Wikipedia article, optionally focused on a topic. |

## osm-mcp-server

Use `osm-mcp-server <command> '<JSON arguments>'`. Run
`osm-mcp-server <command> --help` to get more information.

```sh
osm-mcp-server geocode-address '{"address":"ADDRESS"}'
osm-mcp-server reverse-geocode '{"latitude":LATITUDE,"longitude":LONGITUDE}'
osm-mcp-server get-route-directions '{"from_latitude":FROM_LATITUDE,"from_longitude":FROM_LONGITUDE,"to_latitude":TO_LATITUDE,"to_longitude":TO_LONGITUDE,"mode":"car"}'
```

| Command | Arguments | Description |
|---|---|---|
| `osm-mcp-server geocode-address` | `{address: str}` | Convert an address or place name to geographic coordinates with detailed location information. |
| `osm-mcp-server reverse-geocode` | `{latitude: number, longitude: number}` | Convert geographic coordinates to a detailed address and location description. |
| `osm-mcp-server get-route-directions` | `{from_latitude: number, from_longitude: number, to_latitude: number, to_longitude: number, mode?: str = "car"}` | Calculate detailed route directions between two geographic points. |

## weather

Use `weather <command> '<JSON arguments>'`. Run `weather <command> --help`
to get more information.

```sh
weather get-current-weather '{"location":"40.7128,-74.0060"}'
weather get-weather-forecast '{"location":"40.7128,-74.0060","days":3}'
weather get-hourly-forecast '{"location":"40.7128,-74.0060","hours":12}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather get-current-weather` | `{location: str}` | Get current weather conditions for a location in the United States. Perfect for 'What's the weather like in [US location]?' questions. Covers all US states, territories, and coastal waters. |
| `weather get-weather-forecast` | `{location: str, days?: number = 7}` | Get multi-day weather forecast for a location in the United States. Perfect for 'What's the forecast for [US location]?' questions. Provides detailed day/night forecasts for up to 7 days. |
| `weather get-hourly-forecast` | `{location: str, hours?: number = 24}` | Get hour-by-hour weather forecast for a location in the United States. Perfect for 'What's the hourly forecast?' or 'Will it rain this afternoon in [US location]?' questions. Provides detailed hourly conditions for up to 48 hours. |

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

## e2b-server

Use `e2b-server <command> '<JSON arguments>'`. Run
`e2b-server <command> --help` to get more information.

```sh
e2b-server run-code '{"code":"print(1 + 1)"}'
```

| Command | Arguments | Description |
|---|---|---|
| `e2b-server run-code` | `{code: str}` | Run python code in a secure sandbox by E2B. Using the Jupyter Notebook syntax. |
