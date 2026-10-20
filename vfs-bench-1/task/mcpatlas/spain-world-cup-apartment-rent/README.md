# Spain world cup apartment rent

> My dad told me to get an apartment that was built the same year Spain won its first World Cup. Check the cloud data and tell me if there are any premium one-bedroom units with the best available energy rating built that year. If there are, please provide me with the monthly rent for it.

MCP-Atlas task `68824c643e6ff020bc33990b`.

## The surface

Atlas enables 16 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| notion | 11 | `/notion`, a read-only mount, and `notion`, the MCP arm's own server, on the Notion fake |
| oxylabs | 3 | `oxylabs`, the MCP arm's own server |
| fetch | 1 | `fetch`, the MCP arm's own server |
| mcp-server-code-runner | 1 | `mcp-server-code-runner`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/spain-world-cup-apartment-rent --tools vfs
    uv run python agent/run_agent.py mcpatlas/spain-world-cup-apartment-rent --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py spain-world-cup-apartment-rent

Both arms need `OXYLABS_USERNAME` and `OXYLABS_PASSWORD` (see `.env.example`)
for the live services Atlas enables, the same on both arms.
