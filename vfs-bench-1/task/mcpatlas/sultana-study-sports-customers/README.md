# Sultana study sports customers

> Access the database from the game store to find out how many customers purchased a sports game in the same year that Dr. Sarmin Sultana started their clinical study about the effect of magnesium glycinate. I know it was sometime before 2025.

MCP-Atlas task `689a373e148a49f91233e001`.

## The surface

Atlas enables 15 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| mongodb | 7 | `/mongodb`, a read-only mount, and `mongodb`, the MCP arm's own server, on the run's MongoDB |
| clinicaltrialsgov-mcp-server | 2 | `clinicaltrialsgov-mcp-server`, the MCP arm's own server |
| pubmed | 4 | `pubmed`, the MCP arm's own server |
| desktop-commander | 2 | `/data`, a disk mount |

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

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/sultana-study-sports-customers --tools vfs
    uv run python agent/run_agent.py mcpatlas/sultana-study-sports-customers --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py sultana-study-sports-customers
