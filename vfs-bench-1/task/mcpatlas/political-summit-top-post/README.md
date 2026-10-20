# Political summit top post

> I recently joined the marketing team and I am still getting up to speed. My teammates mentioned that I should look at the social media post that got the most views during the month when the third European Political Community Summit took place. Using the cloud nosql data, could you help me figure out which post that was?.

MCP-Atlas task `688fb11183792b921381bd10`.

## The surface

Atlas enables 14 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| wikipedia | 1 | `wikipedia`, the MCP arm's own server |
| airtable | 1 | `airtable`, the MCP arm's own server, on the Airtable fake |
| mongodb | 4 | `/mongodb`, a read-only mount, and `mongodb`, the MCP arm's own server, on the run's MongoDB |
| context7 | 2 | `context7`, the MCP arm's own server |
| git | 6 | `git`, on the same clones |

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
    uv run python agent/run_agent.py mcpatlas/political-summit-top-post --tools vfs
    uv run python agent/run_agent.py mcpatlas/political-summit-top-post --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py political-summit-top-post
