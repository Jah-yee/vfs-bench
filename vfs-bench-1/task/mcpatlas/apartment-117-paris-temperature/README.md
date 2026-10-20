# Apartment 117 paris temperature

> What was the maximum temperature, in fahrenheit, in paris 8 years after the day we resolved the first service for apartment 117 from our customer feedback database?

MCP-Atlas task `689cd6f8522029b7ad7b1ff9`.

## The surface

Atlas enables 13 tools from nine servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| notion | 2 | `notion`, the MCP arm's own server, on the Notion fake |
| filesystem | 3 | `/data`, a disk mount |
| met-museum | 1 | `met-museum`, the MCP arm's own server |
| clinicaltrialsgov-mcp-server | 1 | `clinicaltrialsgov-mcp-server`, the MCP arm's own server |
| git | 1 | `git`, on the same clones |
| slack | 1 | `slack`, the MCP arm's own server, on the Slack fake |
| oxylabs | 2 | `oxylabs`, the MCP arm's own server |
| weather-data | 1 | `weather-data`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

Notion and Slack are not live. Atlas reads workspaces a user imports from its
own exports; both arms here read mirage's fakes of the two, seeded per run from
those exports by `server/seed/atlas_exports.py`, and the MCP arm's servers are
pointed at them through settings the servers themselves take. The Notion rows
keep the ids and schemas Atlas's recordings carry. The Slack workspace is
mirage's `integ/truth/slack_atlas.json` at the `submodule/mirage` gitlink,
which mirage replays Atlas's recorded Slack calls against; its messages are
moved back the 161 days the export moved them forward, to the dates the
recordings read and the questions ask about, and slack.com is answered by
`server/fakes/slack_host.py`.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/apartment-117-paris-temperature --tools vfs
    uv run python agent/run_agent.py mcpatlas/apartment-117-paris-temperature --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py apartment-117-paris-temperature

Both arms need `OXYLABS_USERNAME`, `OXYLABS_PASSWORD` and `WEATHER_API_KEY`
(see `.env.example`) for the live services Atlas enables, the same on both
arms.
