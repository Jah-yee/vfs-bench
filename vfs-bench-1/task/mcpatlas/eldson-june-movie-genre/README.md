# Éldson's June movie

> I was thinking of watching a movie, and I remembered that in june 2025, my friend eldson recommended a movie on the movies channel. I don't remember the name, but I'd like to know the genre and the imdb score that I have recorded on my computer data.

MCP-Atlas task `689cd6f8522029b7ad7b1fe0`.

Éldson Santos recommended Fight Club in #movie-suggestions on 2025-06-27, and
`/data/Top Movies.csv` has it as a drama rated 8.8.

## The surface

Atlas enables 14 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| filesystem | 6 | `/data`, a disk mount |
| slack | 5 | `/slack`, a read-only mount, and `slack`, the MCP arm's own server, on the Slack fake |
| weather | 1 | `weather`, the MCP arm's own server |
| weather-data | 2 | `weather-data`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/eldson-june-movie-genre --tools vfs
    uv run python agent/run_agent.py mcpatlas/eldson-june-movie-genre --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py eldson-june-movie-genre

Both arms need `WEATHER_API_KEY` (see `.env.example`) for the live services
Atlas enables, the same on both arms.
