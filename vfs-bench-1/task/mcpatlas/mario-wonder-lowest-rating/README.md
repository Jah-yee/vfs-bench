# Mario wonder lowest rating

> What is the lowest employee performance rating, according to our car dealership database, for the year and quarter in which super mario bros wonder was released?

MCP-Atlas task `689af4e653c3905e7b5b2596`.

## The surface

Atlas enables 15 tools from seven servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| airtable | 4 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| filesystem | 3 | `/data`, a disk mount |
| calculator | 1 | `calculator`, the MCP arm's own server |
| exa | 1 | `exa`, the MCP arm's own server |
| notion | 4 | `notion`, the MCP arm's own server, on the Notion fake |
| context7 | 1 | `context7`, the MCP arm's own server |
| slack | 1 | `slack`, the MCP arm's own server, on the Slack fake |

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
    uv run python agent/run_agent.py mcpatlas/mario-wonder-lowest-rating --tools vfs
    uv run python agent/run_agent.py mcpatlas/mario-wonder-lowest-rating --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py mario-wonder-lowest-rating

Both arms need `EXA_API_KEY` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
