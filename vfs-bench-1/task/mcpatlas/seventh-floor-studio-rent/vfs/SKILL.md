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


## notion

Use `notion <command> '<JSON arguments>'`. Run `notion <command> --help` to
get more information.

```sh
notion get-user '{"user_id":"ID"}'
notion post-database-query '{"database_id":"ID","filter":{"property":"Name","rich_text":{"contains":"TEXT"}},"page_size":10}'
notion post-search '{"query":"QUERY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `notion get-user` | `{user_id: str}` | Retrieve a user Error Responses: 400: 400 |
| `notion post-database-query` | `{database_id: str, filter_properties?: list[str], filter?: dict, sorts?: list[{property: str, direction: "ascending" \| "descending"}], start_cursor?: str, page_size?: int = 100, archived?: bool, in_trash?: bool}` | Query a database |
| `notion post-search` | `{query?: str, sort?: {direction?: str, timestamp?: str}, filter?: {value?: str, property?: str}, start_cursor?: str, page_size?: int = 100}` | Search by title |

## clinicaltrialsgov-mcp-server

Use `clinicaltrialsgov-mcp-server <command> '<JSON arguments>'`. Run
`clinicaltrialsgov-mcp-server <command> --help` to get more information.

```sh
clinicaltrialsgov-mcp-server clinicaltrials-get-study '{"nctIds":"NCT00000000","summaryOnly":true}'
clinicaltrialsgov-mcp-server clinicaltrials-list-studies '{"query":{"cond":"CONDITION"},"pageSize":10}'
clinicaltrialsgov-mcp-server clinicaltrials-analyze-trends '{"analysisType":"countByPhase","query":{"cond":"CONDITION"}}'
```

| Command | Arguments | Description |
|---|---|---|
| `clinicaltrialsgov-mcp-server clinicaltrials-get-study` | `{nctIds: str \| list[str], markupFormat?: "markdown" \| "legacy" = "markdown", fields?: list[str], summaryOnly?: bool = false}` | Fetches one or more clinical studies from ClinicalTrials.gov by their NCT IDs. Returns either complete study data or concise summaries for each. |
| `clinicaltrialsgov-mcp-server clinicaltrials-list-studies` | `{query?: {cond?: str, term?: str, locn?: str, titles?: str, intr?: str, outc?: str, spons?: str, id?: str}, filter?: {ids?: list[str], overallStatus?: list["ACTIVE_NOT_RECRUITING" \| "COMPLETED" \| "ENROLLING_BY_INVITATION" \| "NOT_YET_RECRUITING" \| "RECRUITING" \| "SUSPENDED" \| "TERMINATED" \| "WITHDRAWN" \| "UNKNOWN"], geo?: dict, advanced?: str}, fields?: list[str], sort?: list[str], pageSize?: int = 5, pageToken?: str, countTotal?: bool = true}` | Searches for clinical studies using a combination of query terms and filters. Supports pagination, sorting, and geographic filtering. |
| `clinicaltrialsgov-mcp-server clinicaltrials-analyze-trends` | `{query?: {cond?: str, term?: str, locn?: str, titles?: str, intr?: str, outc?: str, spons?: str, id?: str}, filter?: {ids?: list[str], overallStatus?: list["ACTIVE_NOT_RECRUITING" \| "COMPLETED" \| "ENROLLING_BY_INVITATION" \| "NOT_YET_RECRUITING" \| "RECRUITING" \| "SUSPENDED" \| "TERMINATED" \| "WITHDRAWN" \| "UNKNOWN"], geo?: dict, advanced?: str}, analysisType: "countByStatus" \| "countByCountry" \| "countBySponsorType" \| "countByPhase"}` | Performs a statistical analysis on a set of clinical trials, aggregating data by status, country, sponsor, or phase. Use specific query parameters to refine the analysis and filter the studies included in the analysis. The tool can handle up to 5000 studies per analysis. |

## weather-data

Use `weather-data <command> '<JSON arguments>'`. Run
`weather-data <command> --help` to get more information.

```sh
weather-data weather-history '{"q":"CITY","dt":"2025-06-01"}'
weather-data weather-astronomy '{"q":"CITY","dt":"2025-06-01"}'
weather-data weather-search '{"q":"CITY"}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather-data weather-history` | `{q: str, dt: str}` | Get historical weather for a location on a given date (YYYY-MM-DD). Args: q (str): Location query. dt (str): Date in YYYY-MM-DD format. Returns: dict: WeatherAPI history JSON. |
| `weather-data weather-astronomy` | `{q: str, dt: str}` | Get astronomy data (sunrise, sunset, moon) for a date (YYYY-MM-DD). Args: q (str): Location query. dt (str): Date in YYYY-MM-DD format. Returns: dict: WeatherAPI astronomy JSON. |
| `weather-data weather-search` | `{q: str}` | Search for locations matching query. Args: q (str): Location query. Returns: dict: WeatherAPI search JSON. |

## python3

Execute Python code and return stdout and stderr. Code can be pasted into a
`.py` file and run with `python3`. Python cannot launch subprocesses or make
direct network requests. Run the documented service commands directly in
the shell. Use Python for local file processing and generating JSON
arguments.
