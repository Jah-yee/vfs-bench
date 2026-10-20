# Employee 392's fourth service

> Based on our local file /data/food and beverage consumption.csv, where did we eat on the day that employee 392 performed his fourth service according to our cloud customer feedback data?

MCP-Atlas task `689cd6f8522029b7ad7b1fff`.

Employee 392 is `STAFF392` in the Notion Customer Feedback database, with four
services; the fourth to complete did so on 2023-06-17, and the survey row for
17 Jun 2023 in `/data/food and beverage consumption.csv` says Home.

## The surface

Atlas enables 13 tools from eleven servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| filesystem | 2 | `/data`, a disk mount |
| notion | 2 | `notion`, the MCP arm's own server, on the Notion fake |
| met-museum | 1 | `met-museum`, the MCP arm's own server |
| clinicaltrialsgov-mcp-server | 1 | `clinicaltrialsgov-mcp-server`, the MCP arm's own server |
| git | 1 | `git`, on the same clones |
| slack | 1 | `slack`, the MCP arm's own server, on the Slack fake |
| arxiv | 1 | `arxiv`, the MCP arm's own server |
| national-parks | 1 | `national-parks`, the MCP arm's own server |
| oxylabs | 1 | `oxylabs`, the MCP arm's own server |
| memory | 1 | `memory`, the MCP arm's own server |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/employee-fourth-service-meal --tools vfs
    uv run python agent/run_agent.py mcpatlas/employee-fourth-service-meal --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py employee-fourth-service-meal

Both arms need `E2B_API_KEY`, `NPS_API_KEY`, `OXYLABS_USERNAME` and
`OXYLABS_PASSWORD` (see `.env.example`) for the live services Atlas enables,
the same on both arms.
