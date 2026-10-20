# Covid year top spender age group

> I am reviewing my video game store db and want to award a gift card to the customer with the highest total purchases of video games in the year the who declared the covid 19 pandemic. Also, find out which age group that customer belongs to.

MCP-Atlas task `688ba1b3e95696e72dd93ecb`.

The WHO declared COVID-19 a pandemic in 2020. CUST02496 spent the most on
video games that year, 149.93 USD, and is in the 18–25 age group.

## The surface

Atlas enables 16 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| mongodb | 8 | `/mongodb`, a read-only mount, and `mongodb`, the MCP arm's own server, on the run's MongoDB |
| wikipedia | 1 | `wikipedia`, the MCP arm's own server |
| pubmed | 3 | `pubmed`, the MCP arm's own server |
| github | 2 | `gh`, on the GitHub fake |
| weather-data | 2 | `weather-data`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. Every server runs in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7`
started per run, started as upstream's app starts it, and its `tools/list` is
the image's; the divergences are declared on each builder in
`task/mcpatlas/__init__.py`.

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
    uv run python agent/run_agent.py mcpatlas/covid-year-top-spender-age-group --tools vfs
    uv run python agent/run_agent.py mcpatlas/covid-year-top-spender-age-group --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py covid-year-top-spender-age-group

Both arms need `WEATHER_API_KEY` (see `.env.example`) for the live services
Atlas enables, the same on both arms.
