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

You can also use `gh` for GitHub.

## airtable

Use `airtable <command> '<JSON arguments>'`. Run `airtable <command> --help`
to get more information.

```sh
airtable list-bases '{}'
airtable list-tables '{"base_id":"BASE_ID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `airtable list-bases` | `{}` | List all accessible Airtable bases |
| `airtable list-tables` | `{base_id: str}` | List all tables in a base |

## e2b-server

Use `e2b-server <command> '<JSON arguments>'`. Run
`e2b-server <command> --help` to get more information.

```sh
e2b-server run-code '{"code":"print(1 + 1)"}'
```

| Command | Arguments | Description |
|---|---|---|
| `e2b-server run-code` | `{code: str}` | Run python code in a secure sandbox by E2B. Using the Jupyter Notebook syntax. |

## exa

Use `exa <command> '<JSON arguments>'`. Run `exa <command> --help` to get
more information.

```sh
exa web-search-exa '{"query":"QUERY","numResults":5}'
```

| Command | Arguments | Description |
|---|---|---|
| `exa web-search-exa` | `{query: str, numResults?: number}` | Search the web for any topic and get clean, ready-to-use content. |

## wikipedia

Use `wikipedia <command> '<JSON arguments>'`. Run
`wikipedia <command> --help` to get more information.

```sh
wikipedia search-wikipedia '{"query":"QUERY"}'
wikipedia get-article '{"title":"TITLE"}'
```

| Command | Arguments | Description |
|---|---|---|
| `wikipedia search-wikipedia` | `{query: str, limit?: int = 10}` | Search Wikipedia for articles matching a query. |
| `wikipedia get-article` | `{title: str}` | Get the full content of a Wikipedia article. |

## google-maps

Use `google-maps <command> '<JSON arguments>'`. Run
`google-maps <command> --help` to get more information.

```sh
google-maps maps-geocode '{"address":"ADDRESS"}'
```

| Command | Arguments | Description |
|---|---|---|
| `google-maps maps-geocode` | `{address: str}` | Convert an address into geographic coordinates |

## national-parks

Use `national-parks <command> '<JSON arguments>'`. Run
`national-parks <command> --help` to get more information.

```sh
national-parks findParks '{"stateCode":"CA","q":"QUERY"}'
national-parks getParkDetails '{"parkCode":"PARK_CODE"}'
```

| Command | Arguments | Description |
|---|---|---|
| `national-parks findParks` | `{stateCode?: str, q?: str, limit?: number, start?: number, activities?: str}` | Search for national parks based on state, name, activities, or other criteria |
| `national-parks getParkDetails` | `{parkCode: str}` | Get detailed information about a specific national park |

## weather-data

Use `weather-data <command> '<JSON arguments>'`. Run
`weather-data <command> --help` to get more information.

```sh
weather-data weather-current '{"q":"CITY"}'
weather-data weather-forecast '{"q":"CITY","days":3}'
weather-data weather-history '{"q":"CITY","dt":"2025-06-01"}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather-data weather-current` | `{q: str, aqi?: str = "no"}` | Get current weather for a location. Args: q (str): Location query (city name, lat/lon, postal code, etc). aqi (str): Include air quality data ('yes' or 'no'). Returns: dict: WeatherAPI current weather JSON. |
| `weather-data weather-forecast` | `{q: str, days?: int = 1, aqi?: str = "no", alerts?: str = "no"}` | Get weather forecast (1–14 days) for a location. Args: q (str): Location query (city name, lat/lon, postal code, etc). days (int): Number of days (1–14). aqi (str): Include air quality ('yes' or 'no'). alerts (str): Include weather alerts ('yes' or 'no'). Returns: dict: WeatherAPI forecast JSON. |
| `weather-data weather-history` | `{q: str, dt: str}` | Get historical weather for a location on a given date (YYYY-MM-DD). Args: q (str): Location query. dt (str): Date in YYYY-MM-DD format. Returns: dict: WeatherAPI history JSON. |
