# Top three genres wiki links

> I'm doing some business intelligence on videogame sales. Can you grab the customers collection for me and aggregate purchases by game genre? I wish to know the three top genres with a link to each one's wiki page.

MCP-Atlas task `68925f01db31fe35560e3ec5`.

## The surface

Atlas enables 15 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| mongodb | 9 | `/mongodb`, a read-only mount, and `mongodb`, the MCP arm's own server, on the run's MongoDB |
| exa | 1 | `exa`, the MCP arm's own server |
| cli-mcp-server | 1 | the shell itself, over `/data` |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| national-parks | 3 | `national-parks`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run. The
mirage arm mounts none of it, because none of this task's tools reads it.
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
    uv run python agent/run_agent.py mcpatlas/top-three-genres-wiki-links --tools vfs
    uv run python agent/run_agent.py mcpatlas/top-three-genres-wiki-links --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py top-three-genres-wiki-links

Both arms need `EXA_API_KEY`, `E2B_API_KEY` and `NPS_API_KEY` (see
`.env.example`) for the live services Atlas enables, the same on both arms.
