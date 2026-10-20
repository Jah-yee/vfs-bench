# Wings gaming top supplier

> For the second quarter of the year when wings gaming won their first the international dota 2 championship, could you check our car dealership database and see which supplier got the top score? Also, in which particular indicator did they really stand out?

MCP-Atlas task `68925f01db31fe35560e3ec1`.

## The surface

Atlas enables 15 tools from eight servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| airtable | 4 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| exa | 1 | `exa`, the MCP arm's own server |
| weather-data | 2 | `weather-data`, the MCP arm's own server |
| national-parks | 2 | `national-parks`, the MCP arm's own server |
| mongodb | 2 | `mongodb`, the MCP arm's own server, on the run's MongoDB |
| google-maps | 1 | `google-maps`, the MCP arm's own server |
| pubmed | 2 | `pubmed`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/wings-gaming-top-supplier --tools vfs
    uv run python agent/run_agent.py mcpatlas/wings-gaming-top-supplier --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py wings-gaming-top-supplier

Both arms need `EXA_API_KEY`, `WEATHER_API_KEY`, `NPS_API_KEY` and
`GOOGLE_MAPS_API_KEY` (see `.env.example`) for the live services Atlas enables,
the same on both arms.
