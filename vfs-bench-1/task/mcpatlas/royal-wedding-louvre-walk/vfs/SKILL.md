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

## mongodb

Use `mongodb <command> '<JSON arguments>'`. Run `mongodb <command> --help`
to get more information.

```sh
mongodb list-collections '{"database":"DATABASE"}'
mongodb list-databases '{}'
mongodb collection-indexes '{"database":"DATABASE","collection":"COLLECTION"}'
mongodb collection-schema '{"database":"DATABASE","collection":"COLLECTION"}'
mongodb find '{"database":"DATABASE","collection":"COLLECTION","filter":{"FIELD":"VALUE"},"limit":10}'
```

| Command | Arguments | Description |
|---|---|---|
| `mongodb list-collections` | `{database: str}` | List all collections for a given database |
| `mongodb list-databases` | `{}` | List all databases for a MongoDB connection |
| `mongodb collection-indexes` | `{database: str, collection: str}` | Describe the indexes for a collection |
| `mongodb collection-schema` | `{database: str, collection: str}` | Describe the schema for a collection |
| `mongodb find` | `{database: str, collection: str, filter?: dict, projection?: dict, limit?: number = 10, sort?: dict}` | Run a find query against a MongoDB collection |

## airtable

Use `airtable <command> '<JSON arguments>'`. Run `airtable <command> --help`
to get more information.

```sh
airtable get-record '{"base_id":"BASE_ID","table_name":"TABLE","record_id":"RECORD_ID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `airtable get-record` | `{base_id: str, table_name: str, record_id: str}` | Get a single record by its ID |

## wikipedia

Use `wikipedia <command> '<JSON arguments>'`. Run
`wikipedia <command> --help` to get more information.

```sh
wikipedia search-wikipedia '{"query":"QUERY"}'
wikipedia get-article '{"title":"TITLE"}'
wikipedia get-summary '{"title":"TITLE"}'
wikipedia summarize-article-for-query '{"title":"TITLE","query":"QUERY"}'
wikipedia summarize-article-section '{"title":"TITLE","section_title":"SECTION"}'
wikipedia extract-key-facts '{"title":"TITLE","count":5}'
wikipedia get-related-topics '{"title":"TITLE","limit":10}'
wikipedia get-sections '{"title":"TITLE"}'
wikipedia get-links '{"title":"TITLE"}'
```

| Command | Arguments | Description |
|---|---|---|
| `wikipedia search-wikipedia` | `{query: str, limit?: int = 10}` | Search Wikipedia for articles matching a query. |
| `wikipedia get-article` | `{title: str}` | Get the full content of a Wikipedia article. |
| `wikipedia get-summary` | `{title: str}` | Get a summary of a Wikipedia article. |
| `wikipedia summarize-article-for-query` | `{title: str, query: str, max_length?: int = 250}` | Get a summary of a Wikipedia article tailored to a specific query. |
| `wikipedia summarize-article-section` | `{title: str, section_title: str, max_length?: int = 150}` | Get a summary of a specific section of a Wikipedia article. |
| `wikipedia extract-key-facts` | `{title: str, topic_within_article?: str = "", count?: int = 5}` | Extract key facts from a Wikipedia article, optionally focused on a topic. |
| `wikipedia get-related-topics` | `{title: str, limit?: int = 10}` | Get topics related to a Wikipedia article based on links and categories. |
| `wikipedia get-sections` | `{title: str}` | Get the sections of a Wikipedia article. |
| `wikipedia get-links` | `{title: str}` | Get the links contained within a Wikipedia article. |

## google-maps

Use `google-maps <command> '<JSON arguments>'`. Run
`google-maps <command> --help` to get more information.

```sh
google-maps maps-geocode '{"address":"ADDRESS"}'
google-maps maps-reverse-geocode '{"latitude":LATITUDE,"longitude":LONGITUDE}'
google-maps maps-search-places '{"query":"QUERY"}'
google-maps maps-place-details '{"place_id":"PLACE_ID"}'
google-maps maps-distance-matrix '{"origins":["ORIGIN"],"destinations":["DESTINATION"],"mode":"driving"}'
google-maps maps-elevation '{"locations":[{"latitude":LATITUDE,"longitude":LONGITUDE}]}'
google-maps maps-directions '{"origin":"ORIGIN","destination":"DESTINATION","mode":"driving"}'
```

| Command | Arguments | Description |
|---|---|---|
| `google-maps maps-geocode` | `{address: str}` | Convert an address into geographic coordinates |
| `google-maps maps-reverse-geocode` | `{latitude: number, longitude: number}` | Convert coordinates into an address |
| `google-maps maps-search-places` | `{query: str, location?: {latitude?: number, longitude?: number}, radius?: number}` | Search for places using Google Places API |
| `google-maps maps-place-details` | `{place_id: str}` | Get detailed information about a specific place |
| `google-maps maps-distance-matrix` | `{origins: list[str], destinations: list[str], mode?: "driving" \| "walking" \| "bicycling" \| "transit"}` | Calculate travel distance and time for multiple origins and destinations |
| `google-maps maps-elevation` | `{locations: list[{latitude: number, longitude: number}]}` | Get elevation data for locations on the earth |
| `google-maps maps-directions` | `{origin: str, destination: str, mode?: "driving" \| "walking" \| "bicycling" \| "transit"}` | Get directions between two points |
