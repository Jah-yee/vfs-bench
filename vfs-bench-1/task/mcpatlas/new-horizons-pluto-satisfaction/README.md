# New horizons pluto satisfaction

> I was reading about space exploration and came across the milestone when nasa's new horizons spacecraft made its closest approach to pluto. For the second quarter of the same year, check our cloud database records and tell me the average customer satisfactions score for each department, as well as the overall average across all departments for that period.

MCP-Atlas task `689bd255c0422b257e7dfca8`.

## The surface

Atlas enables 17 tools from eleven servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| exa | 1 | `exa`, the MCP arm's own server |
| calculator | 1 | `calculator`, the MCP arm's own server |
| arxiv | 1 | `arxiv`, the MCP arm's own server |
| airtable | 4 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| github | 2 | `gh`, on the GitHub fake |
| git | 1 | `git`, on the same clones |
| pubmed | 1 | `pubmed`, the MCP arm's own server |
| weather-data | 1 | `weather-data`, the MCP arm's own server |
| national-parks | 1 | `national-parks`, the MCP arm's own server |
| met-museum | 2 | `met-museum`, the MCP arm's own server |
| slack | 2 | `/slack`, a read-only mount, and `slack`, the MCP arm's own server, on the Slack fake |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts only its repositories, from a copy taken out of the same
image, at the same paths: this task's tools read `/data` through git alone.
Every server runs in that image, started as upstream's app starts it, and its
`tools/list` is the image's; the divergences are declared on each builder in
`task/mcpatlas/__init__.py`.

Slack is not live. Atlas reads a workspace a user imports from its own export;
both arms here read mirage's fake of the service, seeded per run from that
export as mirage keeps it, `integ/truth/slack_atlas.json` at the
`submodule/mirage` gitlink, which mirage replays Atlas's recorded Slack calls
against, and the MCP arm's server is pointed at it through settings the server
itself takes. The Slack messages are moved back the 161 days the export moved
them forward, to the dates the recordings read and the questions ask about, and
slack.com is answered by `server/fakes/slack_host.py`.

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
    uv run python agent/run_agent.py mcpatlas/new-horizons-pluto-satisfaction --tools vfs
    uv run python agent/run_agent.py mcpatlas/new-horizons-pluto-satisfaction --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py new-horizons-pluto-satisfaction

Both arms need `EXA_API_KEY`, `WEATHER_API_KEY` and `NPS_API_KEY` (see
`.env.example`) for the live services Atlas enables, the same on both arms.
