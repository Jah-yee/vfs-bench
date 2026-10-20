# Donovan birthplace biggest stadium

> I'm researching U.S. soccer history and l want to better understand the background of American soccer talent. I'm planning to visit Landon Donovan's city of birth, can you give me the name of the biggest stadium over there? I also want to know the full address for the closest charging station to it.

MCP-Atlas task `688ba1b3e95696e72dd93ebb`.

## The surface

Atlas enables 19 tools from thirteen servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| context7 | 2 | `context7`, the MCP arm's own server |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| github | 1 | `gh`, on the GitHub fake |
| airtable | 1 | `airtable`, the MCP arm's own server, on the Airtable fake |
| mongodb | 1 | `mongodb`, the MCP arm's own server, on the run's MongoDB |
| pubmed | 1 | `pubmed`, the MCP arm's own server |
| clinicaltrialsgov-mcp-server | 1 | `clinicaltrialsgov-mcp-server`, the MCP arm's own server |
| desktop-commander | 1 | `/data`, a disk mount |
| git | 1 | `git`, on the same clones |
| weather | 2 | `weather`, the MCP arm's own server |
| wikipedia | 2 | `wikipedia`, the MCP arm's own server |
| osm-mcp-server | 4 | `osm-mcp-server`, the MCP arm's own server |
| exa | 1 | `exa`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

MongoDB is not Atlas's cluster. Atlas has a user restore its
`video_game_store` dump into a cluster of their own; both arms here read a
MongoDB started per run and restored from the same dump by
`server/seed/atlas_exports.py`, with each collection's UUID kept, and the MCP
arm's server reaches it on the connection string the template reads. It is
MongoDB 7.0 where an Atlas cluster runs 8.0, because every 8.0 build refuses
Docker Desktop's kernel (SERVER-121912). Replayed through the server, the
recorded calls come back the same but for what a standalone server cannot
match: `list-databases`' sizes and its `config` database, and the first page
an unsorted `find` or `$group` returns, which the recorded cluster did not
keep stable between its own recordings either.

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
    uv run python agent/run_agent.py mcpatlas/donovan-birthplace-biggest-stadium --tools vfs
    uv run python agent/run_agent.py mcpatlas/donovan-birthplace-biggest-stadium --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py donovan-birthplace-biggest-stadium

Both arms need `E2B_API_KEY` and `EXA_API_KEY` (see `.env.example`) for the
live services Atlas enables, the same on both arms.
