# Friend movie recommendation scores

> One of my friends recommended a movie to me in the chat our friend group has. In my personal data, I have a list of the greatest movies I've found, and I want to know if that movie is among them. I'm curious to know if I've already watched it and what the review scores are from both reference sites I use in my data. The same friend also recommended a game with a 64 in its name, and it was amazing.

MCP-Atlas task `689bd255c0422b257e7dfcce`.

## The surface

Atlas enables 16 tools from six servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| filesystem | 4 | `/data`, a disk mount |
| slack | 3 | `/slack`, a read-only mount, and `slack`, the MCP arm's own server, on the Slack fake |
| mcp-code-executor | 1 | `python3`, pyodide |
| airtable | 4 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| exa | 1 | `exa`, the MCP arm's own server |
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
    uv run python agent/run_agent.py mcpatlas/friend-movie-recommendation-scores --tools vfs
    uv run python agent/run_agent.py mcpatlas/friend-movie-recommendation-scores --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py friend-movie-recommendation-scores

Both arms need `EXA_API_KEY` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
