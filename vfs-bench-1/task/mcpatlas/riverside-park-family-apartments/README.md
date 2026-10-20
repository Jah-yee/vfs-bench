# Riverside Park family apartments

> I'm looking for an apartment for the family from my graph who hosted the event in riverside park. They are looking for a furniture equipped apartment with one room for each family member plus one extra. Also, the father reminded me that his daughter is afraid of heights, so they prefer apartments on the third floor or below. According to the company's data, could you provide the property manager identification for the three apartments that fit these criteria with the lowest rent?

MCP-Atlas task `689cd6f8522029b7ad7b1fdd`.

The memory graph's family who hosted the Riverside Park event has three
members, so four bedrooms. The three cheapest furnished four-bedroom apartments
on the third floor or below in the Notion Real Estate database are managed by
MNGR766 ($1,621), MNGR183 ($1,635) and MNGR469 ($1,655).

## The surface

Atlas enables 15 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| notion | 3 | `notion`, the MCP arm's own server, on the Notion fake |
| memory | 1 | `memory`, the MCP arm's own server |
| filesystem | 5 | `/data`, a disk mount |
| oxylabs | 3 | `oxylabs`, the MCP arm's own server |
| github | 3 | `gh`, on the GitHub fake |

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
    uv run python agent/run_agent.py mcpatlas/riverside-park-family-apartments --tools vfs
    uv run python agent/run_agent.py mcpatlas/riverside-park-family-apartments --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py riverside-park-family-apartments

Both arms need `OXYLABS_USERNAME` and `OXYLABS_PASSWORD` (see `.env.example`)
for the live services Atlas enables, the same on both arms.
