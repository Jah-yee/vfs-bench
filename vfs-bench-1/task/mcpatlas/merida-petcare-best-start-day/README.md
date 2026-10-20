# Merida petcare best start day

> What is the start day with the highest weekly profits? My partner is convinced that our petcare is being affected by the constellations here in merida, yucatan, but I think is ridiculous, and I want to use the file in my computer to prove it, so he cannot say I don't have real proof. What was the moon phase that day?

MCP-Atlas task `689a373e148a49f91233e02b`.

## The surface

Atlas enables 17 tools from nine servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| weather-data | 3 | `weather-data`, the MCP arm's own server |
| google-workspace | 1 | `/calendar`, a read-only mount, and `google-workspace`, the MCP arm's own server, on the Calendar fake |
| filesystem | 3 | `/data`, a disk mount |
| fetch | 1 | `fetch`, the MCP arm's own server |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| context7 | 2 | `context7`, the MCP arm's own server |
| clinicaltrialsgov-mcp-server | 1 | `clinicaltrialsgov-mcp-server`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |
| desktop-commander | 4 | `/data`, a disk mount |

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
    uv run python agent/run_agent.py mcpatlas/merida-petcare-best-start-day --tools vfs
    uv run python agent/run_agent.py mcpatlas/merida-petcare-best-start-day --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py merida-petcare-best-start-day

Both arms need `WEATHER_API_KEY` and `E2B_API_KEY` (see `.env.example`) for the
live services Atlas enables, the same on both arms.
