# Bronco turnover lowest eth

> Using the cloud database, check my local files to see the lowest amount of eth sent according to my trading history in the same month and year when the turnover rate for the bronco model was 0.17

MCP-Atlas task `68952adeba1c2ad4e6a5db37`.

## The surface

Atlas enables 16 tools from seven servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| cli-mcp-server | 2 | the shell itself, over `/data` |
| airtable | 5 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| github | 1 | `gh`, on the GitHub fake |
| open-library | 1 | `open-library`, the MCP arm's own server |
| weather-data | 3 | `weather-data`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |
| met-museum | 3 | `met-museum`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/bronco-turnover-lowest-eth --tools vfs
    uv run python agent/run_agent.py mcpatlas/bronco-turnover-lowest-eth --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py bronco-turnover-lowest-eth

Both arms need `WEATHER_API_KEY` (see `.env.example`) for the live services
Atlas enables, the same on both arms.
