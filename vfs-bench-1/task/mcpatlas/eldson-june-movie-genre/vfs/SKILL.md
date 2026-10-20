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

## slack

Use `slack <command> '<JSON arguments>'`. Run `slack <command> --help` to
get more information.

```sh
slack channels-list '{"channel_types":"public_channel,private_channel"}'
slack conversations-history '{"channel_id":"CHANNEL_ID","limit":"1d"}'
slack conversations-replies '{"channel_id":"CHANNEL_ID","thread_ts":"1234567890.123456"}'
slack conversations-search-messages '{"search_query":"QUERY","filter_in_channel":"CHANNEL_ID"}'
```

| Command | Arguments | Description |
|---|---|---|
| `slack channels-list` | `{channel_types: str, cursor?: str, limit?: number = 100, sort?: str}` | Get list of channels |
| `slack conversations-add-message` | `{channel_id: str, content_type?: str = "text/markdown", payload?: str, thread_ts?: str}` | Add a message to a public channel, private channel, or direct message (DM, or IM) conversation by channel_id and thread_ts. |
| `slack conversations-history` | `{channel_id: str, cursor?: str, include_activity_messages?: bool = false, limit?: str = "1d"}` | Get messages from the channel (or DM) by channel_id, the last row/column in the response is used as 'cursor' parameter for pagination if not empty |
| `slack conversations-replies` | `{channel_id: str, cursor?: str, include_activity_messages?: bool = false, limit?: str = "1d", thread_ts: str}` | Get a thread of messages posted to a conversation by channelID and thread_ts, the last row/column in the response is used as 'cursor' parameter for pagination if not empty |
| `slack conversations-search-messages` | `{cursor?: str = "", filter_date_after?: str, filter_date_before?: str, filter_date_during?: str, filter_date_on?: str, filter_in_channel?: str, filter_in_im_or_mpim?: str, filter_threads_only?: bool, filter_users_from?: str, filter_users_with?: str, limit?: number = 20, search_query?: str}` | Search messages in a public channel, private channel, or direct message (DM, or IM) conversation using filters. All filters are optional, if not provided then search_query is required. |

## weather

Use `weather <command> '<JSON arguments>'`. Run `weather <command> --help`
to get more information.

```sh
weather find-weather-stations '{"location":"40.7128,-74.0060"}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather find-weather-stations` | `{location: str, limit?: number = 10}` | Find weather observation stations near a location in the United States. Useful for getting station-specific data, finding data sources, or understanding which stations provide weather data for an area. Includes ASOS, AWOS, and other automated weather stations. |

## weather-data

Use `weather-data <command> '<JSON arguments>'`. Run
`weather-data <command> --help` to get more information.

```sh
weather-data weather-history '{"q":"CITY","dt":"2025-06-01"}'
weather-data weather-astronomy '{"q":"CITY","dt":"2025-06-01"}'
```

| Command | Arguments | Description |
|---|---|---|
| `weather-data weather-history` | `{q: str, dt: str}` | Get historical weather for a location on a given date (YYYY-MM-DD). Args: q (str): Location query. dt (str): Date in YYYY-MM-DD format. Returns: dict: WeatherAPI history JSON. |
| `weather-data weather-astronomy` | `{q: str, dt: str}` | Get astronomy data (sunrise, sunset, moon) for a date (YYYY-MM-DD). Args: q (str): Location query. dt (str): Date in YYYY-MM-DD format. Returns: dict: WeatherAPI astronomy JSON. |
