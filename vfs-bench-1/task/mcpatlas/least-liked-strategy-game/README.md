# Least liked strategy game

> I’m looking into whether some less-loved strategy games still manage to perform well. Between 2021 and 2023, which strategy title sold over $200 worth of copies despite being the least liked by buyers? If more than one game fits that description, go with the one that earned the most money. I’d like to know which game it is, how well it sold, and how poorly it was rated. This is all based on cloud data from the video game store.

MCP-Atlas task `688ba1b3e95696e72dd93ee0`.

## The surface

Atlas enables 17 tools from seven servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| airtable | 1 | `airtable`, the MCP arm's own server, on the Airtable fake |
| mongodb | 6 | `/mongodb`, a read-only mount, and `mongodb`, the MCP arm's own server, on the run's MongoDB |
| osm-mcp-server | 4 | `osm-mcp-server`, the MCP arm's own server |
| clinicaltrialsgov-mcp-server | 2 | `clinicaltrialsgov-mcp-server`, the MCP arm's own server |
| git | 2 | `git`, on the same clones |
| desktop-commander | 1 | `/data`, a disk mount |
| cli-mcp-server | 1 | the shell itself, over `/data` |

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

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/least-liked-strategy-game --tools vfs
    uv run python agent/run_agent.py mcpatlas/least-liked-strategy-game --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py least-liked-strategy-game
