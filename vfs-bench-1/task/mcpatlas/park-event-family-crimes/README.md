# Park event family crimes

> I was reviewing my event records in the knowledge graph, and I wanted to verify crime data in the area. From my local system, I have a file containing crime records. Tell me which family organized the event held at a park, which family members are attending, and how many crimes in my file occurred in any parks.

MCP-Atlas task `686d2c79e1db37ea23ddda15`.

## The surface

Atlas enables 15 tools from six servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| calculator | 1 | `calculator`, the MCP arm's own server |
| memory | 3 | `memory`, the MCP arm's own server |
| filesystem | 6 | `/data`, a disk mount |
| oxylabs | 1 | `oxylabs`, the MCP arm's own server |
| notion | 3 | `notion`, the MCP arm's own server, on the Notion fake |
| google-workspace | 1 | `/calendar`, a read-only mount, and `google-workspace`, the MCP arm's own server, on the Calendar fake |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

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
    uv run python agent/run_agent.py mcpatlas/park-event-family-crimes --tools vfs
    uv run python agent/run_agent.py mcpatlas/park-event-family-crimes --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py park-event-family-crimes

Both arms need `OXYLABS_USERNAME` and `OXYLABS_PASSWORD` (see `.env.example`)
for the live services Atlas enables, the same on both arms.
