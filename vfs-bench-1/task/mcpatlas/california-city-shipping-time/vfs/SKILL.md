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

## mongodb

Use `mongodb <command> '<JSON arguments>'`. Run `mongodb <command> --help`
to get more information.

```sh
mongodb list-collections '{"database":"DATABASE"}'
mongodb list-databases '{}'
mongodb collection-indexes '{"database":"DATABASE","collection":"COLLECTION"}'
mongodb collection-schema '{"database":"DATABASE","collection":"COLLECTION"}'
mongodb find '{"database":"DATABASE","collection":"COLLECTION","filter":{"FIELD":"VALUE"},"limit":10}'
mongodb aggregate '{"database":"DATABASE","collection":"COLLECTION","pipeline":[{"$group":{"_id":"$FIELD","total":{"$sum":1}}}]}'
```

| Command | Arguments | Description |
|---|---|---|
| `mongodb list-collections` | `{database: str}` | List all collections for a given database |
| `mongodb list-databases` | `{}` | List all databases for a MongoDB connection |
| `mongodb collection-indexes` | `{database: str, collection: str}` | Describe the indexes for a collection |
| `mongodb collection-schema` | `{database: str, collection: str}` | Describe the schema for a collection |
| `mongodb find` | `{database: str, collection: str, filter?: dict, projection?: dict, limit?: number = 10, sort?: dict}` | Run a find query against a MongoDB collection |
| `mongodb aggregate` | `{database: str, collection: str, pipeline: list[dict]}` | Run an aggregation against a MongoDB collection |

## oxylabs

Use `oxylabs <command> '<JSON arguments>'`. Run `oxylabs <command> --help`
to get more information.

```sh
oxylabs google-search-scraper '{"query":"QUERY"}'
oxylabs amazon-search-scraper '{"query":"QUERY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `oxylabs google-search-scraper` | `{query: str, parse?: bool = true, render?: "" \| "html" = "", user_agent_type?: "" \| "desktop" \| "desktop_chrome" \| "desktop_firefox" \| "desktop_safari" \| "desktop_edge" \| "desktop_opera" \| "mobile" \| "mobile_ios" \| "mobile_android" \| "tablet" = "", start_page?: int = 0, pages?: int = 0, limit?: int = 0, domain?: str = "", geo_location?: str = "", locale?: str = "", ad_mode?: bool = false, output_format?: "" \| "links" \| "md" \| "html" = ""}` | Scrape Google Search results. |
| `oxylabs amazon-search-scraper` | `{query: str, category_id?: str = "", merchant_id?: str = "", currency?: str = "", parse?: bool = true, render?: "" \| "html" = "", user_agent_type?: "" \| "desktop" \| "desktop_chrome" \| "desktop_firefox" \| "desktop_safari" \| "desktop_edge" \| "desktop_opera" \| "mobile" \| "mobile_ios" \| "mobile_android" \| "tablet" = "", start_page?: int = 0, pages?: int = 0, domain?: str = "", geo_location?: str = "", locale?: str = "", output_format?: "" \| "links" \| "md" \| "html" = ""}` | Scrape Amazon search results. |

## mcp-server-code-runner

Use `mcp-server-code-runner <command> '<JSON arguments>'`. Run
`mcp-server-code-runner <command> --help` to get more information.

```sh
mcp-server-code-runner run-code '{"code":"print(1 + 1)","languageId":"python"}'
```

| Command | Arguments | Description |
|---|---|---|
| `mcp-server-code-runner run-code` | `{code: str, languageId: "javascript" \| "php" \| "python" \| "perl" \| "perl6" \| "ruby" \| "go" \| "lua" \| "groovy" \| "powershell" \| "bat" \| "shellscript" \| "fsharp" \| "csharp" \| "vbscript" \| "typescript" \| "coffeescript" \| "scala" \| "swift" \| "julia" \| "crystal" \| "ocaml" \| "r" \| "applescript" \| "clojure" \| "racket" \| "scheme" \| "ahk" \| "autoit" \| "dart" \| "haskell" \| "nim" \| "lisp" \| "kit" \| "v" \| "sass" \| "scss"}` | Run code snippet and return the result. |

## osm-mcp-server

Use `osm-mcp-server <command> '<JSON arguments>'`. Run
`osm-mcp-server <command> --help` to get more information.

```sh
osm-mcp-server geocode-address '{"address":"ADDRESS"}'
osm-mcp-server find-nearby-places '{"latitude":LATITUDE,"longitude":LONGITUDE,"radius":1000,"limit":20}'
osm-mcp-server get-route-directions '{"from_latitude":FROM_LATITUDE,"from_longitude":FROM_LONGITUDE,"to_latitude":TO_LATITUDE,"to_longitude":TO_LONGITUDE,"mode":"car"}'
```

| Command | Arguments | Description |
|---|---|---|
| `osm-mcp-server geocode-address` | `{address: str}` | Convert an address or place name to geographic coordinates with detailed location information. |
| `osm-mcp-server find-nearby-places` | `{latitude: number, longitude: number, radius?: number = 1000, categories?: list[str] = null, limit?: int = 20}` | Discover points of interest and amenities near a specific location. |
| `osm-mcp-server get-route-directions` | `{from_latitude: number, from_longitude: number, to_latitude: number, to_longitude: number, mode?: str = "car"}` | Calculate detailed route directions between two geographic points. |

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

## weather-data

Use `weather-data <command> '<JSON arguments>'`. Run
`weather-data <command> --help` to get more information.

```sh
weather-data weather-astronomy '{"q":"CITY","dt":"2025-06-01"}'
weather-data weather-search '{"q":"CITY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather-data weather-astronomy` | `{q: str, dt: str}` | Get astronomy data (sunrise, sunset, moon) for a date (YYYY-MM-DD). Args: q (str): Location query. dt (str): Date in YYYY-MM-DD format. Returns: dict: WeatherAPI astronomy JSON. |
| `weather-data weather-search` | `{q: str}` | Search for locations matching query. Args: q (str): Location query. Returns: dict: WeatherAPI search JSON. |

## weather

Use `weather <command> '<JSON arguments>'`. Run `weather <command> --help`
to get more information.

```sh
weather find-weather-stations '{"location":"40.7128,-74.0060"}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather find-weather-stations` | `{location: str, limit?: number = 10}` | Find weather observation stations near a location in the United States. Useful for getting station-specific data, finding data sources, or understanding which stations provide weather data for an area. Includes ASOS, AWOS, and other automated weather stations. |

## python3

Execute Python code and return stdout and stderr. Code can be pasted into a
`.py` file and run with `python3`. Python cannot launch subprocesses or make
direct network requests. Run the documented service commands directly in
the shell. Use Python for local file processing and generating JSON
arguments.
