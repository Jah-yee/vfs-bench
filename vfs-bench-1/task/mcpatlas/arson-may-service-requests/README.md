# Arson and May service requests

> I'm attempting to do some detective work regarding a case of arson close by that happened in May of 2017. Can you check the online customer feedback database for service requests and see if any request dates collide with those in the local crime records file for that May?

MCP-Atlas task `689cd6f8522029b7ad7b1fe3`.

`/data/Crime_records.csv` holds one arson in May 2017, CRIME696 on 2017-05-29.
The latest of the Notion Customer Feedback database's 44 interactions that
month is on 2017-05-28, so no date is shared.

## The surface

Atlas enables 15 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| notion | 8 | `/notion`, a read-only mount, and `notion`, the MCP arm's own server, on the Notion fake |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| filesystem | 3 | `/data`, a disk mount |
| arxiv | 1 | `arxiv`, the MCP arm's own server |
| github | 2 | `gh`, on the GitHub fake |

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

GitHub is not live. This task's row asks about nothing on GitHub, and live
GitHub answers whatever the token reaches, private repositories included, so
both arms here read mirage's GitHub fake, started per run and holding nothing:
a search finds nothing and a repository is not found, as GitHub answers for
what it does not hold. The MCP arm's server takes no base URL, so
`redirect/github/github_hook.mjs` moves api.github.com inside its `fetch`; `gh`
is given the fake's URL.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/arson-may-service-requests --tools vfs
    uv run python agent/run_agent.py mcpatlas/arson-may-service-requests --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py arson-may-service-requests

Both arms need `E2B_API_KEY` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
