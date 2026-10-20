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

## rail-12306

Use `rail-12306 <command> '<JSON arguments>'`. Run
`rail-12306 <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `rail-12306 get-current-date` | `{}` | 获取当前日期，以上海时区（Asia/Shanghai, UTC+8）为准，返回格式为 "yyyy-MM-dd"。主要用于解析用户提到的相对日期（如“明天”、“下周三”），提供准确的日期输入。 |
| `rail-12306 get-stations-code-in-city` | `{city: str}` | 通过中文城市名查询该城市 **所有** 火车站的名称及其对应的 `station_code`，结果是一个包含多个车站信息的列表。 — `city`: 中文城市名称，例如："北京", "上海" |
| `rail-12306 get-station-code-of-citys` | `{citys: str}` | 通过中文城市名查询代表该城市的 `station_code`。 — `citys`: 要查询的城市，比如"北京"。若要查询多个城市，请用\|分割，比如"北京\|上海"。 |
| `rail-12306 get-station-code-by-names` | `{stationNames: str}` | 通过具体的中文车站名查询其 `station_code` 和车站名。 — `stationNames`: 具体的中文车站名称，例如："北京南", "上海虹桥"。若要查询多个站点，请用\|分割，比如"北京南\|上海虹桥"。 |
| `rail-12306 get-station-by-telecode` | `{stationTelecode: str}` | 通过车站的 `station_telecode` 查询车站的详细信息，包括名称、拼音、所属城市等。此接口主要用于在已知 `telecode` 的情况下获取更完整的车站数据，或用于特殊查询及调试目的。一般用户对话流程中较少直接触发。 — `stationTelecode`: 车站的 `station_telecode` (3位字母编码) |
| `rail-12306 get-tickets` | `{date: str, fromStation: str, toStation: str, trainFilterFlags?: str = "", earliestStartTime?: number = 0, latestStartTime?: number = 24, sortFlag?: str = "", sortReverse?: bool = false, limitedNum?: number = 0, format?: str = "text"}` | 查询12306余票信息。 — `date`: 查询日期，格式为 "yyyy-MM-dd"。如果用户提供的是相对日期（如“明天”），请务必先调用 `get-current-date` 接口获取当前日期，并计算出目标日期。; `fromStation`: 出发地的中文名或站点的 `station_code`（可通过 `get-station-code-by-names` 或 `get-station-code-of-citys` 接口查询得到）; `toStation`: 到达地的中文名或站点的 `station_code`（可通过 `get-station-code-by-names` 或 `get-station-code-of-citys` 接口查询得到）; `trainFilterFlags`: 车次筛选条件，默认为空，即不筛选。支持多个标志同时筛选。例如用户说“高铁票”，则应使用 "G"。可选标志：[G(高铁/城际),D(动车),Z(直达特快),T(特快),K(快速),O(其他),F(复兴号),S(智能动车组)]; `earliestStartTime`: 最早出发时间（0-24），默认为0。; `latestStartTime`: 最迟出发时间（0-24），默认为24。; `sortFlag`: 排序方式，默认为空，即不排序。仅支持单一标识。可选标志：[startTime(出发时间从早到晚), arriveTime(抵达时间从早到晚), duration(历时从短到长)]; `sortReverse`: 是否逆向排序结果，默认为false。仅在设置了sortFlag时生效。; `limitedNum`: 返回的余票数量限制，默认为0，即不限制。; `format`: 返回结果格式，默认为text，建议使用text与csv。可选标志：[text, csv, json] |
| `rail-12306 get-interline-tickets` | `{date: str, fromStation: str, toStation: str, middleStation?: str = "", showWZ?: bool = false, trainFilterFlags?: str = "", earliestStartTime?: number = 0, latestStartTime?: number = 24, sortFlag?: str = "", sortReverse?: bool = false, limitedNum?: number = 10, format?: str = "text"}` | 查询12306中转余票信息。尚且只支持查询前十条。 — `date`: 查询日期，格式为 "yyyy-MM-dd"。如果用户提供的是相对日期（如“明天”），请务必先调用 `get-current-date` 接口获取当前日期，并计算出目标日期。; `fromStation`: 出发地的中文名或站点的 `station_code`（可通过 `get-station-code-by-names` 或 `get-station-code-of-citys` 接口查询得到）; `toStation`: 到达地的中文名或站点的 `station_code`（可通过 `get-station-code-by-names` 或 `get-station-code-of-citys` 接口查询得到）; `middleStation`: 中转地的中文或站点的 `station_code`（可通过 `get-station-code-by-names` 或 `get-station-code-of-citys` 接口查询得到）。该参数可选。; `showWZ`: 是否显示无座车，默认不显示无座车。; `trainFilterFlags`: 车次筛选条件，默认为空。从以下标志中选取多个条件组合[G(高铁/城际),D(动车),Z(直达特快),T(特快),K(快速),O(其他),F(复兴号),S(智能动车组)]; `earliestStartTime`: 最早出发时间（0-24），默认为0。; `latestStartTime`: 最迟出发时间（0-24），默认为24。; `sortFlag`: 排序方式，默认为空，即不排序。仅支持单一标识。可选标志：[startTime(出发时间从早到晚), arriveTime(抵达时间从早到晚), duration(历时从短到长)]; `sortReverse`: 是否逆向排序结果，默认为false。仅在设置了sortFlag时生效。; `limitedNum`: 返回的中转余票数量限制，默认为10。; `format`: 返回结果格式，默认为text，建议使用text。可选标志：[text, json] |
| `rail-12306 get-train-route-stations` | `{trainCode: str, departDate: str, format?: str = "text"}` | 查询特定列车车次在指定区间内的途径车站、到站时间、出发时间及停留时间等详细经停信息。当用户询问某趟具体列车的经停站时使用此接口。 — `trainCode`: 要查询的车次 `train_code`，例如"G1033"。; `departDate`: 列车出发的日期 (格式: yyyy-MM-dd)。如果用户提供的是相对日期，请务必先调用 `get-current-date` 解析。; `format`: 返回结果格式，默认为text，建议使用text。可选标志：[text, json] |

## git

Use `git --help` for Git operations on workspace repositories.

## python3

Execute Python code directly under the agent workspace and return stdout
and stderr. Code can be pasted into a `.py` file and run with `python3`.

Python cannot launch subprocesses or make direct network requests. Run the
documented service commands directly in the shell. Use Python for local
file processing and generating JSON arguments.
