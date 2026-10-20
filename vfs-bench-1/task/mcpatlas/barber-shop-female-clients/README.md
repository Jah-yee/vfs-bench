# Barber shop female clients

> I'm reviewing the barber shop data in my PC files and'd like to know what percentage of clients were female and the average age of those female clients. Round both the percentage and average age to two decimal places

MCP-Atlas task `689bd255c0422b257e7dfcc5`.

## The surface

Atlas enables 14 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| filesystem | 10 | `/data`, a disk mount |
| mcp-code-executor | 2 | `python3`, pyodide |
| arxiv | 1 | `arxiv`, the MCP arm's own server |
| airtable | 1 | `airtable`, the MCP arm's own server, on the Airtable fake |

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
    uv run python agent/run_agent.py mcpatlas/barber-shop-female-clients --tools vfs
    uv run python agent/run_agent.py mcpatlas/barber-shop-female-clients --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py barber-shop-female-clients
