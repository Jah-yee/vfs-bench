# Tina turner fewest leavings

> Which department in my cloud dealership database had the fewest leavings in the first quarter of the year tina turner passed away?

MCP-Atlas task `689bd255c0422b257e7dfcb1`.

## The surface

Atlas enables 15 tools from six servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| arxiv | 1 | `arxiv`, the MCP arm's own server |
| oxylabs | 3 | `oxylabs`, the MCP arm's own server |
| national-parks | 2 | `national-parks`, the MCP arm's own server |
| airtable | 5 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| memory | 3 | `memory`, the MCP arm's own server |
| fetch | 1 | `fetch`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. Every server runs in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7`
started per run, started as upstream's app starts it, and its `tools/list` is
the image's; the divergences are declared on each builder in
`task/mcpatlas/__init__.py`.

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
    uv run python agent/run_agent.py mcpatlas/tina-turner-fewest-leavings --tools vfs
    uv run python agent/run_agent.py mcpatlas/tina-turner-fewest-leavings --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py tina-turner-fewest-leavings

Both arms need `OXYLABS_USERNAME`, `OXYLABS_PASSWORD` and `NPS_API_KEY` (see
`.env.example`) for the live services Atlas enables, the same on both arms.
