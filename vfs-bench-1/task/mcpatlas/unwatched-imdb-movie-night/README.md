# Unwatched imdb movie night

> From my local movie data, what's the highest-rated movie I haven't watched yet on imdb? I need it for my july 2025 family movie night, so please also remind me of the date and time it is scheduled.

MCP-Atlas task `689bd255c0422b257e7dfcaf`.

## The surface

Atlas enables 14 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| exa | 1 | `exa`, the MCP arm's own server |
| filesystem | 10 | `/data`, a disk mount |
| google-workspace | 1 | `/calendar`, a read-only mount, and `google-workspace`, the MCP arm's own server, on the Calendar fake |
| mcp-code-executor | 2 | `python3`, pyodide |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

The calendar is not live. Atlas has a user import its `.ics` into a fresh
Google account; both arms here read mirage's Google Workspace fake, seeded per
run from the same export by `server/seed/atlas_exports.py` -- Google's own
event ids, the two weekly series expanded into the instances Google lists, in
the New York zone the recordings read -- and googleapis.com is answered by
`server/fakes/slack_host.py`. All 22 recorded `list_events` calls replay byte
for byte.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/unwatched-imdb-movie-night --tools vfs
    uv run python agent/run_agent.py mcpatlas/unwatched-imdb-movie-night --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py unwatched-imdb-movie-night

Both arms need `EXA_API_KEY` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
