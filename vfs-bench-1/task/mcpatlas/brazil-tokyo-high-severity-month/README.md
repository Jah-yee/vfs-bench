# Brazil tokyo high severity month

> According to our local data, between the years the FIFA World Cup was held in Brazil and the year the Tokyo Olympic Games were held, which month had the highest number of high-severity incidents? And, for that month, what were the specific types of high severity crimes and the exact dates of each incident?

MCP-Atlas task `689e0b1d9c8e2ac413c1f20c`.

## The surface

Atlas enables 15 tools from six servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| fetch | 1 | `fetch`, the MCP arm's own server |
| filesystem | 5 | `/data`, a disk mount |
| memory | 3 | `memory`, the MCP arm's own server |
| oxylabs | 3 | `oxylabs`, the MCP arm's own server |
| notion | 2 | `notion`, the MCP arm's own server, on the Notion fake |

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
    uv run python agent/run_agent.py mcpatlas/brazil-tokyo-high-severity-month --tools vfs
    uv run python agent/run_agent.py mcpatlas/brazil-tokyo-high-severity-month --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py brazil-tokyo-high-severity-month

Both arms need `E2B_API_KEY`, `OXYLABS_USERNAME` and `OXYLABS_PASSWORD` (see
`.env.example`) for the live services Atlas enables, the same on both arms.
