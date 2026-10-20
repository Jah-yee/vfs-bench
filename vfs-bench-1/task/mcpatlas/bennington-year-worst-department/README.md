# Bennington year worst department

> In my car dealership database, between the sales and service departments, which one had the worst performance in the third quarter of the year chester bennington died, and what was the lowest individual score in that department?

MCP-Atlas task `688fb11183792b921381bd0d`.

## The surface

Atlas enables 15 tools from seven servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| airtable | 5 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| exa | 1 | `exa`, the MCP arm's own server |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| cli-mcp-server | 2 | the shell itself, over `/data` |
| weather-data | 3 | `weather-data`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |
| wikipedia | 2 | `wikipedia`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/bennington-year-worst-department --tools vfs
    uv run python agent/run_agent.py mcpatlas/bennington-year-worst-department --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py bennington-year-worst-department

Both arms need `EXA_API_KEY`, `E2B_API_KEY` and `WEATHER_API_KEY` (see
`.env.example`) for the live services Atlas enables, the same on both arms.
