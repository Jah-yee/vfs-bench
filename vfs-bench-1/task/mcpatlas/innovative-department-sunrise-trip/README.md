# Innovative department sunrise trip

> I want to reward the most innovative department, according to their employee performance, with the highest score of the first quarter of 2020, using my PC files, with a trip to the state where the sun rose earliest on april first of that year, pick one between ny and wa.

MCP-Atlas task `689bd255c0422b257e7dfcb5`.

## The surface

Atlas enables 17 tools from seven servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| airtable | 5 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| calculator | 1 | `calculator`, the MCP arm's own server |
| memory | 3 | `memory`, the MCP arm's own server |
| weather-data | 3 | `weather-data`, the MCP arm's own server |
| slack | 1 | `slack`, the MCP arm's own server, on the Slack fake |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| pubmed | 3 | `pubmed`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. Every server runs in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7`
started per run, started as upstream's app starts it, and its `tools/list` is
the image's; the divergences are declared on each builder in
`task/mcpatlas/__init__.py`.

Slack is not live. Atlas reads a workspace a user imports from its own export;
both arms here read mirage's fake of the service, seeded per run from that
export as mirage keeps it, `integ/truth/slack_atlas.json` at the
`submodule/mirage` gitlink, which mirage replays Atlas's recorded Slack calls
against, and the MCP arm's server is pointed at it through settings the server
itself takes. The Slack messages are moved back the 161 days the export moved
them forward, to the dates the recordings read and the questions ask about, and
slack.com is answered by `server/fakes/slack_host.py`.

Airtable is not live. Atlas ships its base as a share link a user copies into
an account of their own; both arms here read mirage's fake of the service,
seeded per run with the base as mirage captured it from that link,
`integ/truth/airtable_atlas.json` at the `submodule/mirage` gitlink, which
mirage replays Atlas's recorded Airtable calls against. Upstream's server takes
no base URL, so it reaches the fake through a proxy and a CA of this repo's,
`server/fakes/slack_host.py`.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/innovative-department-sunrise-trip --tools vfs
    uv run python agent/run_agent.py mcpatlas/innovative-department-sunrise-trip --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py innovative-department-sunrise-trip

Both arms need `WEATHER_API_KEY` and `E2B_API_KEY` (see `.env.example`) for the
live services Atlas enables, the same on both arms.
