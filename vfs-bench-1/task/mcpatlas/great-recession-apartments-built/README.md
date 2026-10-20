# Great recession apartments built

> There was a great recession that affected housing prices in the united states in the first decade of the 21st century. For my historical research, check my database and find apartments that were built in the year after the recession officially ended, and of those, tell me whether the furnished or unfurnished apartments had the highest average rent. Don't include any units that are only semi-furnished

MCP-Atlas task `689cd6f8522029b7ad7b200a`.

## The surface

Atlas enables 14 tools from eight servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| notion | 4 | `/notion`, a read-only mount, and `notion`, the MCP arm's own server, on the Notion fake |
| oxylabs | 2 | `oxylabs`, the MCP arm's own server |
| mcp-code-executor | 1 | `python3`, pyodide |
| cli-mcp-server | 2 | the shell itself, over `/data` |
| context7 | 2 | `context7`, the MCP arm's own server |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| fetch | 1 | `fetch`, the MCP arm's own server |
| memory | 1 | `memory`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/great-recession-apartments-built --tools vfs
    uv run python agent/run_agent.py mcpatlas/great-recession-apartments-built --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py great-recession-apartments-built

Both arms need `OXYLABS_USERNAME`, `OXYLABS_PASSWORD` and `E2B_API_KEY` (see
`.env.example`) for the live services Atlas enables, the same on both arms.
