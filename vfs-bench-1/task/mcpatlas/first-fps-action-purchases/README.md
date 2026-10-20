# First fps action purchases

> I'm investigating the relationship between video games of different generations based on our customer data. What was the total number of action video game purchases made in 2023 by customers with active memberships who were at least 5 years old at the end of the year in which the first documented first-person shooter game was developed?

MCP-Atlas task `688fb11183792b921381bd55`.

## The surface

Atlas enables 16 tools from eight servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| mongodb | 5 | `/mongodb`, a read-only mount, and `mongodb`, the MCP arm's own server, on the run's MongoDB |
| wikipedia | 2 | `wikipedia`, the MCP arm's own server |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| pubmed | 4 | `pubmed`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |
| git | 1 | `git`, on the same clones |
| clinicaltrialsgov-mcp-server | 1 | `clinicaltrialsgov-mcp-server`, the MCP arm's own server |
| context7 | 1 | `context7`, the MCP arm's own server |

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

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/first-fps-action-purchases --tools vfs
    uv run python agent/run_agent.py mcpatlas/first-fps-action-purchases --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py first-fps-action-purchases

Both arms need `E2B_API_KEY` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
