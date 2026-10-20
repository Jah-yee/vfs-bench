# Tokyo premiere temperature root

> What's the square root of the average temperature in celsius in tokyo on the day of the premiere of the film miley cyrus something beautiful?

MCP-Atlas task `689bd255c0422b257e7dfcd9`.

## The surface

Atlas enables 13 tools from twelve servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| weather-data | 1 | `weather-data`, the MCP arm's own server |
| calculator | 1 | `calculator`, the MCP arm's own server |
| exa | 1 | `exa`, the MCP arm's own server |
| met-museum | 1 | `met-museum`, the MCP arm's own server |
| clinicaltrialsgov-mcp-server | 1 | `clinicaltrialsgov-mcp-server`, the MCP arm's own server |
| slack | 1 | `slack`, the MCP arm's own server, on the Slack fake |
| notion | 2 | `notion`, the MCP arm's own server, on the Notion fake |
| arxiv | 1 | `arxiv`, the MCP arm's own server |
| national-parks | 1 | `national-parks`, the MCP arm's own server |
| oxylabs | 1 | `oxylabs`, the MCP arm's own server |
| memory | 1 | `memory`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run. The
mirage arm mounts none of it, because none of this task's tools reads it.
Every server runs in that image, started as upstream's app starts it, and its
`tools/list` is the image's; the divergences are declared on each builder in
`task/mcpatlas/__init__.py`.

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
    uv run python agent/run_agent.py mcpatlas/tokyo-premiere-temperature-root --tools vfs
    uv run python agent/run_agent.py mcpatlas/tokyo-premiere-temperature-root --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py tokyo-premiere-temperature-root

Both arms need `WEATHER_API_KEY`, `EXA_API_KEY`, `NPS_API_KEY`,
`OXYLABS_USERNAME` and `OXYLABS_PASSWORD` (see `.env.example`) for the live
services Atlas enables, the same on both arms.
