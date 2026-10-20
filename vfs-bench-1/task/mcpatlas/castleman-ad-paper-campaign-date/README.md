# Castleman ad paper campaign date

> I'm researching papers on advertisement effectiveness and comparing it to our own online database advertising data. There's a 2024 paper by jane castleman that deals with ad control effectiveness, can you get me the abstract? I believe it mentions ad locality, for which I will also need to ask you for the date of our campaign with the biggest engagement rate, started during the 2015-2023 period, and its locality.

MCP-Atlas task `689cd6f8522029b7ad7b2024`.

## The surface

Atlas enables 15 tools from six servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| notion | 5 | `notion`, the MCP arm's own server, on the Notion fake |
| arxiv | 1 | `arxiv`, the MCP arm's own server |
| fetch | 1 | `fetch`, the MCP arm's own server |
| memory | 2 | `memory`, the MCP arm's own server |
| slack | 4 | `/slack`, a read-only mount, and `slack`, the MCP arm's own server, on the Slack fake |
| whois | 2 | `whois`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run. The
mirage arm mounts none of it, because none of this task's tools reads it.
Every server runs in that image, started as upstream's app starts it, and its
`tools/list` is the image's; the divergences are declared on each builder in
`task/mcpatlas/__init__.py`.

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
    uv run python agent/run_agent.py mcpatlas/castleman-ad-paper-campaign-date --tools vfs
    uv run python agent/run_agent.py mcpatlas/castleman-ad-paper-campaign-date --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py castleman-ad-paper-campaign-date
