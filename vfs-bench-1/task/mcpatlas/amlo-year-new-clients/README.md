# Amlo year new clients

> In the same year that andres manuel lopez obrador was elected in Mexico, how many new clients bought video games? Retrieve the data from the database.

MCP-Atlas task `6890e7fd2516f66b0a628e5d`.

López Obrador was elected in 2018, and 56 new clients bought video games
that year, for 5,645.76 in sales.

## The surface

Atlas enables 15 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| wikipedia | 4 | `wikipedia`, the MCP arm's own server |
| mongodb | 6 | `/mongodb`, a read-only mount, and `mongodb`, the MCP arm's own server, on the run's MongoDB |
| git | 3 | `git`, on the same clones |
| github | 2 | `gh`, on the GitHub fake |

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
    uv run python agent/run_agent.py mcpatlas/amlo-year-new-clients --tools vfs
    uv run python agent/run_agent.py mcpatlas/amlo-year-new-clients --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py amlo-year-new-clients
