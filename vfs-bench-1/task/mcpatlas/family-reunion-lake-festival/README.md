# Family reunion lake festival

> We have scheduled our annual family reunion for the 1st week of aug 2025 in an la neighborhood; there is a lake there. Can you check how many days there are between the end date of the festival held there and our reunion?

MCP-Atlas task `689bd255c0422b257e7dfd08`.

## The surface

Atlas enables 17 tools from eight servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| context7 | 2 | `context7`, the MCP arm's own server |
| calculator | 1 | `calculator`, the MCP arm's own server |
| fetch | 1 | `fetch`, the MCP arm's own server |
| mcp-server-code-runner | 1 | `mcp-server-code-runner`, the MCP arm's own server |
| git | 6 | `git`, on the same clones |
| national-parks | 4 | `national-parks`, the MCP arm's own server |
| google-workspace | 1 | `/calendar`, a read-only mount, and `google-workspace`, the MCP arm's own server, on the Calendar fake |
| exa | 1 | `exa`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/family-reunion-lake-festival --tools vfs
    uv run python agent/run_agent.py mcpatlas/family-reunion-lake-festival --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py family-reunion-lake-festival

Both arms need `NPS_API_KEY` and `EXA_API_KEY` (see `.env.example`) for the
live services Atlas enables, the same on both arms.
