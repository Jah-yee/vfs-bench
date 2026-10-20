# Kobe year twitter posts

> I need to know, from the cloud nosql video game store database, how many twitter posts were made in the year kobe bryant passed away.

MCP-Atlas task `68a398aa2f58036e8d45edf6`.

Kobe Bryant died in 2020, and the `Social Media` collection holds 64
Twitter posts dated that year.

## The surface

Atlas enables 16 tools from seven servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| mongodb | 4 | `/mongodb`, a read-only mount, and `mongodb`, the MCP arm's own server, on the run's MongoDB |
| wikipedia | 2 | `wikipedia`, the MCP arm's own server |
| memory | 3 | `memory`, the MCP arm's own server |
| pubmed | 3 | `pubmed`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |
| github | 2 | `gh`, on the GitHub fake |
| fetch | 1 | `fetch`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/kobe-year-twitter-posts --tools vfs
    uv run python agent/run_agent.py mcpatlas/kobe-year-twitter-posts --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py kobe-year-twitter-posts
