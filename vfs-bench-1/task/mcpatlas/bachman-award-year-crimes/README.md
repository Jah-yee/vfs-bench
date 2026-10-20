# Bachman award year crimes

> I'm working on a case, and I think it might be related to a crime registered in my personal logs. Could you help me find the identification code and type of crimes that occurred in the same year the author who used the pseudonym richard bachman was awarded the national medal of arts?

MCP-Atlas task `6888e207a34beb25cfedda86`.

## The surface

Atlas enables 14 tools from seven servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| memory | 3 | `memory`, the MCP arm's own server |
| notion | 2 | `notion`, the MCP arm's own server, on the Notion fake |
| fetch | 1 | `fetch`, the MCP arm's own server |
| open-library | 3 | `open-library`, the MCP arm's own server |
| whois | 1 | `whois`, the MCP arm's own server |
| national-parks | 2 | `national-parks`, the MCP arm's own server |
| cli-mcp-server | 2 | the shell itself, over `/data` |

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

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/bachman-award-year-crimes --tools vfs
    uv run python agent/run_agent.py mcpatlas/bachman-award-year-crimes --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py bachman-award-year-crimes

Both arms need `NPS_API_KEY` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
