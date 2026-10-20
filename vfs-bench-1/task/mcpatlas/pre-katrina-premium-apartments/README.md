# Pre katrina premium apartments

> I'm thinking of going apartment hunting. I have this idea that the apartments built years before the year Hurricane Katrina happened are a good investment, so check my database for any premium 2-bedroom apartment with a one-year lease built before that. I'm on a tight budget, so only give me the apartment numbers of the apartments with a monthly rent of less than 2500 USD and a deposit of less than 1000 USD.

MCP-Atlas task `68834223448b8fe04df2a595`.

## The surface

Atlas enables 15 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| notion | 11 | `/notion`, a read-only mount, and `notion`, the MCP arm's own server, on the Notion fake |
| google-workspace | 1 | `/calendar`, a read-only mount, and `google-workspace`, the MCP arm's own server, on the Calendar fake |
| oxylabs | 2 | `oxylabs`, the MCP arm's own server |
| calculator | 1 | `calculator`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. Every server runs in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7`
started per run, started as upstream's app starts it, and its `tools/list` is
the image's; the divergences are declared on each builder in
`task/mcpatlas/__init__.py`.

Notion is not live. Atlas reads a workspace a user imports from its own export;
both arms here read mirage's fake of the service, seeded per run from that
export by `server/seed/atlas_exports.py`, and the MCP arm's server is pointed
at it through settings the server itself takes. The Notion rows keep the ids
and schemas Atlas's recordings carry.

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
    uv run python agent/run_agent.py mcpatlas/pre-katrina-premium-apartments --tools vfs
    uv run python agent/run_agent.py mcpatlas/pre-katrina-premium-apartments --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py pre-katrina-premium-apartments

Both arms need `OXYLABS_USERNAME` and `OXYLABS_PASSWORD` (see `.env.example`)
for the live services Atlas enables, the same on both arms.
