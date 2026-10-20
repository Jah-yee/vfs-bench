# Q4 2023 department performance

> While checking the hiring records of our car dealership network, I doubted the average performance score per department (rounded to two digits) for the last quarter of 2023. Could you get this info, and according to the one with the highest average score, find an article by greta galliani, with the name of the department included in the title. What's its title?

MCP-Atlas task `689bd255c0422b257e7dfcad`.

## The surface

Atlas enables 15 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| airtable | 5 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| mcp-code-executor | 4 | `python3`, pyodide |
| national-parks | 4 | `national-parks`, the MCP arm's own server |
| calculator | 1 | `calculator`, the MCP arm's own server |
| arxiv | 1 | `arxiv`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

Airtable is not live. Atlas ships its base as a share link a user copies into
an account of their own; both arms here read mirage's fake of the service,
seeded per run with the base as mirage captured it from that link,
`integ/truth/airtable_atlas.json` at the `submodule/mirage` gitlink, which
mirage replays Atlas's recorded Airtable calls against. Upstream's server takes
no base URL, so it reaches the fake through a proxy and a CA of this repo's,
`server/fakes/slack_host.py`.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/q4-2023-department-performance --tools vfs
    uv run python agent/run_agent.py mcpatlas/q4-2023-department-performance --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py q4-2023-department-performance

Both arms need `NPS_API_KEY` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
