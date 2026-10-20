# December 2023 mobile cpc

> Please consider the information for campaigns that were started in December 2023 of my digital organization system on advertising, and determine the average cpc from mobile devices (round to three decimals).

MCP-Atlas task `688a441c1a0d2e5c93853e4f`.

## The surface

Atlas enables 13 tools from three servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| notion | 11 | `/notion`, a read-only mount, and `notion`, the MCP arm's own server, on the Notion fake |
| mcp-code-executor | 1 | `python3`, pyodide |
| calculator | 1 | `calculator`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/december-2023-mobile-cpc --tools vfs
    uv run python agent/run_agent.py mcpatlas/december-2023-mobile-cpc --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py december-2023-mobile-cpc
