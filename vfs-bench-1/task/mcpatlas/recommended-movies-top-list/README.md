# Recommended movies on the top list

> What movies of the recommended in the channel of the server are already in the list of my computer for the best movies? I want to find the best suggestions. What are the ratings of those matching movies?

MCP-Atlas task `689e0b1d9c8e2ac413c1f225`.

Three of #movie-suggestions' movies are in `/data/Top Movies.csv`: Reservoir
Dogs (8.3), The Matrix (8.7) and Fight Club (8.8).

## The surface

Atlas enables 17 tools from nine servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| slack | 3 | `/slack`, a read-only mount, and `slack`, the MCP arm's own server, on the Slack fake |
| filesystem | 3 | `/data`, a disk mount |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| context7 | 2 | `context7`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |
| weather-data | 1 | `weather-data`, the MCP arm's own server |
| cli-mcp-server | 2 | the shell itself, over `/data` |
| oxylabs | 2 | `oxylabs`, the MCP arm's own server |
| pubmed | 2 | `pubmed`, the MCP arm's own server |

`cli-mcp-server` runs `ls`, `cat` and `find` in the tree and nothing else,
which the shell over `/data` already does.

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

Slack is not live. Atlas reads a workspace a user imports from its own export;
both arms here read mirage's fake of the service, seeded per run from that
export as mirage keeps it, `integ/truth/slack_atlas.json` at the
`submodule/mirage` gitlink, which mirage replays Atlas's recorded Slack calls
against, and the MCP arm's server is pointed at it through settings the server
itself takes. The Slack messages are moved back the 161 days the export moved
them forward, to the dates the recordings read and the questions ask about, and
slack.com is answered by `server/fakes/slack_host.py`.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/recommended-movies-top-list --tools vfs
    uv run python agent/run_agent.py mcpatlas/recommended-movies-top-list --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py recommended-movies-top-list

Both arms need `E2B_API_KEY`, `OXYLABS_USERNAME`, `OXYLABS_PASSWORD` and
`WEATHER_API_KEY` (see `.env.example`) for the live services Atlas enables, the
same on both arms.
