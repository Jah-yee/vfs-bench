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

## mongodb

Use `mongodb <command> '<JSON arguments>'`. Run `mongodb <command> --help`
to get more information.

```sh
mongodb list-collections '{"database":"DATABASE"}'
mongodb list-databases '{}'
mongodb collection-schema '{"database":"DATABASE","collection":"COLLECTION"}'
mongodb find '{"database":"DATABASE","collection":"COLLECTION","filter":{"FIELD":"VALUE"},"limit":10}'
mongodb count '{"database":"DATABASE","collection":"COLLECTION","query":{"FIELD":"VALUE"}}'
mongodb aggregate '{"database":"DATABASE","collection":"COLLECTION","pipeline":[{"$group":{"_id":"$FIELD","total":{"$sum":1}}}]}'
```

| Command | Arguments | Description |
|---|---|---|
| `mongodb list-collections` | `{database: str}` | List all collections for a given database |
| `mongodb list-databases` | `{}` | List all databases for a MongoDB connection |
| `mongodb collection-schema` | `{database: str, collection: str}` | Describe the schema for a collection |
| `mongodb find` | `{database: str, collection: str, filter?: dict, projection?: dict, limit?: number = 10, sort?: dict}` | Run a find query against a MongoDB collection |
| `mongodb count` | `{database: str, collection: str, query?: dict}` | Gets the number of documents in a MongoDB collection using db.collection.count() and query as an optional filter parameter |
| `mongodb aggregate` | `{database: str, collection: str, pipeline: list[dict]}` | Run an aggregation against a MongoDB collection |

## airtable

Use `airtable <command> '<JSON arguments>'`. Run `airtable <command> --help`
to get more information.

```sh
airtable get-record '{"base_id":"BASE_ID","table_name":"TABLE","record_id":"RECORD_ID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `airtable get-record` | `{base_id: str, table_name: str, record_id: str}` | Get a single record by its ID |

## osm-mcp-server

Use `osm-mcp-server <command> '<JSON arguments>'`. Run
`osm-mcp-server <command> --help` to get more information.

```sh
osm-mcp-server get-route-directions '{"from_latitude":FROM_LATITUDE,"from_longitude":FROM_LONGITUDE,"to_latitude":TO_LATITUDE,"to_longitude":TO_LONGITUDE,"mode":"car"}'
osm-mcp-server find-schools-nearby '{"latitude":LATITUDE,"longitude":LONGITUDE,"radius":2000}'
osm-mcp-server analyze-neighborhood '{"latitude":LATITUDE,"longitude":LONGITUDE,"radius":1000}'
osm-mcp-server find-parking-facilities '{"latitude":LATITUDE,"longitude":LONGITUDE,"radius":1000}'
```

| Command | Arguments | Description |
|---|---|---|
| `osm-mcp-server get-route-directions` | `{from_latitude: number, from_longitude: number, to_latitude: number, to_longitude: number, mode?: str = "car"}` | Calculate detailed route directions between two geographic points. |
| `osm-mcp-server find-schools-nearby` | `{latitude: number, longitude: number, radius?: number = 2000, education_levels?: list[str] = null}` | Locate educational institutions near a specific location, filtered by education level. |
| `osm-mcp-server analyze-neighborhood` | `{latitude: number, longitude: number, radius?: number = 1000}` | Generate a comprehensive neighborhood analysis focused on livability factors. |
| `osm-mcp-server find-parking-facilities` | `{latitude: number, longitude: number, radius?: number = 1000, parking_type?: str = null}` | Locate parking facilities near a specific location. |

## clinicaltrialsgov-mcp-server

Use `clinicaltrialsgov-mcp-server <command> '<JSON arguments>'`. Run
`clinicaltrialsgov-mcp-server <command> --help` to get more information.

```sh
clinicaltrialsgov-mcp-server clinicaltrials-get-study '{"nctIds":"NCT00000000","summaryOnly":true}'
clinicaltrialsgov-mcp-server clinicaltrials-list-studies '{"query":{"cond":"CONDITION"},"pageSize":10}'
```

| Command | Arguments | Description |
|---|---|---|
| `clinicaltrialsgov-mcp-server clinicaltrials-get-study` | `{nctIds: str \| list[str], markupFormat?: "markdown" \| "legacy" = "markdown", fields?: list[str], summaryOnly?: bool = false}` | Fetches one or more clinical studies from ClinicalTrials.gov by their NCT IDs. Returns either complete study data or concise summaries for each. |
| `clinicaltrialsgov-mcp-server clinicaltrials-list-studies` | `{query?: {cond?: str, term?: str, locn?: str, titles?: str, intr?: str, outc?: str, spons?: str, id?: str}, filter?: {ids?: list[str], overallStatus?: list["ACTIVE_NOT_RECRUITING" \| "COMPLETED" \| "ENROLLING_BY_INVITATION" \| "NOT_YET_RECRUITING" \| "RECRUITING" \| "SUSPENDED" \| "TERMINATED" \| "WITHDRAWN" \| "UNKNOWN"], geo?: dict, advanced?: str}, fields?: list[str], sort?: list[str], pageSize?: int = 5, pageToken?: str, countTotal?: bool = true}` | Searches for clinical studies using a combination of query terms and filters. Supports pagination, sorting, and geographic filtering. |
