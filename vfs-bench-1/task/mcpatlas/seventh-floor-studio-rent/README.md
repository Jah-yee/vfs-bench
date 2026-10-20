# Seventh-floor studio rent

> Could you search the company data for an apartment? I have a 10% discount on the rent for being part of the company, and I want to use it. I'm looking for an apartment with one bedroom plus another room to be my studio. I have my own furniture, and I love to have a great view, so it should be at least on the seventh floor. According to my personal data, how much is left from my average profit I made in the pet store compared to the discounted rent of the cheapest apartment?

MCP-Atlas task `689cd6f8522029b7ad7b2037`.

The Notion Real Estate database's cheapest unfurnished two-bedroom apartment on
the seventh floor or above rents for $1,531, $1,377.90 after the discount. The
pet store's weekly profits in `/data/Pet Care 2023 Weekly Financials.csv`
average $6,593.65, which leaves $5,215.75.

## The surface

Atlas enables 14 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| weather-data | 3 | `weather-data`, the MCP arm's own server |
| clinicaltrialsgov-mcp-server | 3 | `clinicaltrialsgov-mcp-server`, the MCP arm's own server |
| notion | 3 | `notion`, the MCP arm's own server, on the Notion fake |
| filesystem | 4 | `/data`, a disk mount |
| mcp-code-executor | 1 | `python3` |

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
    uv run python agent/run_agent.py mcpatlas/seventh-floor-studio-rent --tools vfs
    uv run python agent/run_agent.py mcpatlas/seventh-floor-studio-rent --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py seventh-floor-studio-rent

Both arms need `WEATHER_API_KEY` (see `.env.example`) for the live services
Atlas enables, the same on both arms.
