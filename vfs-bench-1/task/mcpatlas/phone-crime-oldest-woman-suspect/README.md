# Phone crime oldest woman suspect

> I have a record in my local files about a criminal phone incident from the past where the person believed to be responsible was a woman, the oldest such individual recorded in the file, who has not been aprehended yet.
>
> Tell me the number of reported instances per 10 thousand people related to the global health crisis happening during the year this crime took place, considering only the three month standard yearly period where this date would be included. The information for data related to this health crisis is also in my local files.

MCP-Atlas task `688ba1b3e95696e72dd93e92`.

## The surface

Atlas enables 14 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| mongodb | 6 | `/mongodb`, a read-only mount, and `mongodb`, the MCP arm's own server, on the run's MongoDB |
| wikipedia | 2 | `wikipedia`, the MCP arm's own server |
| desktop-commander | 4 | `/data`, a disk mount |
| exa | 1 | `exa`, the MCP arm's own server |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/phone-crime-oldest-woman-suspect --tools vfs
    uv run python agent/run_agent.py mcpatlas/phone-crime-oldest-woman-suspect --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py phone-crime-oldest-woman-suspect

Both arms need `EXA_API_KEY` and `E2B_API_KEY` (see `.env.example`) for the
live services Atlas enables, the same on both arms.
