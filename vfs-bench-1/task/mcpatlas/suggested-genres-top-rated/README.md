# Top-rated movie per suggested genre

> Tell me the movie with the highest imdb rating in the local database for the genres of each movie suggested in the group chat.

MCP-Atlas task `689cd6f8522029b7ad7b2030`.

Three of #movie-suggestions' movies are in `/data/Top Movies.csv`: Fight Club
(drama), The Matrix (action) and Reservoir Dogs (crime). The top-rated of each
genre there is The Shawshank Redemption (9.3), The Dark Knight (9) and The
Godfather (9.2).

## The surface

Atlas enables 15 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| filesystem | 3 | `/data`, a disk mount |
| slack | 3 | `/slack`, a read-only mount, and `slack`, the MCP arm's own server, on the Slack fake |
| fetch | 1 | `fetch`, the MCP arm's own server |
| memory | 2 | `memory`, the MCP arm's own server |
| github | 6 | `gh`, on the GitHub fake |

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
    uv run python agent/run_agent.py mcpatlas/suggested-genres-top-rated --tools vfs
    uv run python agent/run_agent.py mcpatlas/suggested-genres-top-rated --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py suggested-genres-top-rated
