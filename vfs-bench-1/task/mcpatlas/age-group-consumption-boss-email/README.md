# Age-group consumption and the boss's email

> I'm finishing my work and need to email it to my boss, mike. But first, I need to get some information from a personal file. Could you provide me with the most consumed drinks and food categories for each age demographic? Also, I need my boss's email address. He uses it in the company's data, but I can't remember what it is.

MCP-Atlas task `689e0b1d9c8e2ac413c1f257`.

The survey is `/data/food and beverage consumption.csv`: fast food, Italian,
pizza, fast food and seafood are the most consumed food types for 18-24 through
55-64, and beer, water, beer, water and water the most consumed drinks. The
boss is the Notion workspace's member Michael Dumle, `mcpdumle@gmail.com`.

## The surface

Atlas enables 15 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| notion | 8 | `notion`, the MCP arm's own server, on the Notion fake |
| mcp-code-executor | 1 | `python3` |
| filesystem | 3 | `/data`, a disk mount |
| git | 1 | `git`, on the same clones |
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
    uv run python agent/run_agent.py mcpatlas/age-group-consumption-boss-email --tools vfs
    uv run python agent/run_agent.py mcpatlas/age-group-consumption-boss-email --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py age-group-consumption-boss-email
