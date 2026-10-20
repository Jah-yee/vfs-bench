# qtwatcher1999's movie

> Check my local movie data and tell me if I have already watched the movie suggested by the user qtwatcher1999 in the chat channel dedicated to movie recommendations.

MCP-Atlas task `689cd6f8522029b7ad7b1ff7`.

qtwatcher1999 suggested Reservoir Dogs in #movie-suggestions, and `/data/Top
Movies.csv` does not mark it watched.

## The surface

Atlas enables 15 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| slack | 4 | `/slack`, a read-only mount, and `slack`, the MCP arm's own server, on the Slack fake |
| filesystem | 6 | `/data`, a disk mount |
| oxylabs | 2 | `oxylabs`, the MCP arm's own server |
| fetch | 1 | `fetch`, the MCP arm's own server |
| memory | 2 | `memory`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/qtwatcher-movie-watched --tools vfs
    uv run python agent/run_agent.py mcpatlas/qtwatcher-movie-watched --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py qtwatcher-movie-watched

Both arms need `OXYLABS_USERNAME` and `OXYLABS_PASSWORD` (see `.env.example`)
for the live services Atlas enables, the same on both arms.
