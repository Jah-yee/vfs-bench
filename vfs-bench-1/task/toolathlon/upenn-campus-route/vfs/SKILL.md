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

## google-map

Use `google-map <command> '<JSON arguments>'`. Run
`google-map <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `google-map geocode` | `{address: str}` | Convert an address into geographic coordinates — `address`: The address to geocode |
| `google-map reverse-geocode` | `{latitude: number, longitude: number}` | Convert coordinates into an address — `latitude`: Latitude coordinate; `longitude`: Longitude coordinate |
| `google-map search-places` | `{query: str, location?: {latitude?: number, longitude?: number}, radius?: number}` | Search for places using Google Places API — `query`: Search query; `location`: Optional center point for the search; `radius`: Search radius in meters (max 50000) |
| `google-map place-details` | `{place_id: str}` | Get detailed information about a specific place — `place_id`: The place ID to get details for |
| `google-map distance-matrix` | `{origins: list[str], destinations: list[str], mode?: "driving" \| "walking" \| "bicycling" \| "transit"}` | Calculate travel distance and time for multiple origins and destinations — `origins`: Array of origin addresses or coordinates; `destinations`: Array of destination addresses or coordinates; `mode`: Travel mode (driving, walking, bicycling, transit) |
| `google-map elevation` | `{locations: list[{latitude: number, longitude: number}]}` | Get elevation data for locations on the earth — `locations`: Array of locations to get elevation for |
| `google-map directions` | `{origin: str, destination: str, mode?: "driving" \| "walking" \| "bicycling" \| "transit"}` | Get directions between two points — `origin`: Starting point address or coordinates; `destination`: Ending point address or coordinates; `mode`: Travel mode (driving, walking, bicycling, transit) |

## git

Use `git --help` for Git operations on workspace repositories.

## python3

Execute Python code directly under the agent workspace and return stdout
and stderr. Code can be pasted into a `.py` file and run with `python3`.

Python cannot launch subprocesses or make direct network requests. Run the
documented service commands directly in the shell. Use Python for local
file processing and generating JSON arguments.
