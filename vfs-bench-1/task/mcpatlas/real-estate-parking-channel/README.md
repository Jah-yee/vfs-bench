# Apartments with parking, and a real-estate channel

> Lately, I've been getting a lot of questions about apartments that include a spot to park your car, at least 3 bedrooms and already equipped with all the furniture a person would need. Can you check how many of those we have in our real estate cloud data? I'm considering sharing the results via our chat app, but could you verify if there's a specific real estate channel I should send this info to?

MCP-Atlas task `687ebf5ff5a578e0055a455e`.

389 of the Notion Real Estate database's 4,898 apartments have parking, three
or more bedrooms and furniture, and none of the workspace's six Slack channels
is about real estate.

## The surface

Atlas enables 13 tools from three servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| notion | 9 | `/notion`, a read-only mount, and `notion`, the MCP arm's own server, on the Notion fake |
| slack | 3 | `/slack`, a read-only mount, and `slack`, the MCP arm's own server, on the Slack fake |
| memory | 1 | `memory`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

Notion and Slack are not live. Atlas reads workspaces a user imports from its
own exports; both arms here read mirage's fakes of the two, seeded per run from
those exports by `server/seed/atlas_exports.py`, and the MCP arm's servers are
pointed at them through settings the servers themselves take. The Notion rows
keep the ids and schemas Atlas's recordings carry. The Slack workspace is
mirage's `integ/truth/slack_atlas.json` at the `submodule/mirage` gitlink,
which mirage replays Atlas's recorded Slack calls against; its messages are
moved back the 161 days the export moved them forward, to the dates the
recordings read and the questions ask about, and slack.com is answered by
`server/fakes/slack_host.py`.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/real-estate-parking-channel --tools vfs
    uv run python agent/run_agent.py mcpatlas/real-estate-parking-channel --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py real-estate-parking-channel
