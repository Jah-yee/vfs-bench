---
name: workspace-commands
description: The shell commands and task tools available in this workspace.
---

# Available commands

Python (`python` or `python3`), Perl, JavaScript/Node.js, and TypeScript
runtimes are unavailable. Use the shell commands and task CLIs documented
below; do not probe for or attempt to install other runtimes.

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip

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

## youtube

Use `youtube <command> '<JSON arguments>'`. Run `youtube <command> --help`
to get more information.

| Command | Arguments | Description |
|---|---|---|
| `youtube videos-getVideo` | `{videoId: str, parts?: list[str]}` | Get detailed information about a YouTube video — `videoId`: The YouTube video ID; `parts`: Parts of the video to retrieve |
| `youtube videos-searchVideos` | `{query: str, maxResults?: number}` | Search for videos on YouTube — `query`: Search query; `maxResults`: Maximum number of results to return |
| `youtube transcripts-getTranscript` | `{videoId: str, language?: str}` | Get the transcript of a YouTube video — `videoId`: The YouTube video ID; `language`: Language code for the transcript |
| `youtube channels-getChannel` | `{channelId: str}` | Get information about a YouTube channel — `channelId`: The YouTube channel ID |
| `youtube channels-listVideos` | `{channelId: str, maxResults?: number, sortOrder?: "newest" \| "oldest" \| "popular"}` | Start a new channel videos list with sorting options (creates a new list session) — `channelId`: The YouTube channel ID; `maxResults`: Maximum number of results per page (max 20, default 20); `sortOrder`: Sort order for videos |
| `youtube channels-navigateList` | `{listId: str, page: number}` | Navigate within an existing list session (prev/next page, jump to specific page) — `listId`: The list session ID from a previous listVideos call; `page`: Page number to navigate to (1-based) |
| `youtube playlists-getPlaylist` | `{playlistId: str}` | Get information about a YouTube playlist — `playlistId`: The YouTube playlist ID |
| `youtube playlists-getPlaylistItems` | `{playlistId: str, maxResults?: number}` | Get videos in a YouTube playlist — `playlistId`: The YouTube playlist ID; `maxResults`: Maximum number of results to return |
| `youtube playlists-searchPlaylists` | `{query: str, maxResults?: number}` | Search for playlists on YouTube — `query`: Search query for playlists; `maxResults`: Maximum number of results to return |

## youtube-transcript

Use `youtube-transcript <command> '<JSON arguments>'`. Run
`youtube-transcript <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `youtube-transcript get-transcript` | `{url: str, lang?: str = "en"}` | Retrieves the transcript of a YouTube video. — `url`: The URL of the YouTube video; `lang`: The preferred language for the transcript |

## gh

Use `gh --help` for the registered GitHub commands. Repository, issue, pull-request, release and API operations use the same GitHub service as upstream MCP. Use `gh <command> --help` for arguments and output options.
