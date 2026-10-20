# July 13 movie watchlist

> Do I have any appointment to watch a movie with my girlfriend this 13 of july, 2025? I want something new to watch, and I stored my watchlist on my computer for the best movies I get recommendations for. Can you tell me the first result in my list that I haven't seen? And what is its mpa?

MCP-Atlas task `68993ef3cf3e953b8ab83fbd`.

## The surface

Atlas enables 15 tools from six servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| desktop-commander | 5 | `/data`, a disk mount |
| ddg-search | 2 | `ddg-search`, the MCP arm's own server |
| google-workspace | 1 | `/calendar`, a read-only mount, and `google-workspace`, the MCP arm's own server, on the Calendar fake |
| github | 2 | `gh`, on the GitHub fake |
| git | 3 | `git`, on the same clones |
| open-library | 2 | `open-library`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

The calendar is not live. Atlas has a user import its `.ics` into a fresh
Google account; both arms here read mirage's Google Workspace fake, seeded per
run from the same export by `server/seed/atlas_exports.py` -- Google's own
event ids, the two weekly series expanded into the instances Google lists, in
the New York zone the recordings read -- and googleapis.com is answered by
`server/fakes/slack_host.py`. All 22 recorded `list_events` calls replay byte
for byte.

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
    uv run python agent/run_agent.py mcpatlas/july-13-movie-watchlist --tools vfs
    uv run python agent/run_agent.py mcpatlas/july-13-movie-watchlist --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py july-13-movie-watchlist
