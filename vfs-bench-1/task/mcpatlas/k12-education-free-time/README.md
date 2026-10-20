# K12 education free time

> Lately, I've been interested in k-12 education. Do I know anyone with experience in this field according to my graph? Also, I would like to read an article on the matter by christopher d pfledderer. To discuss the matter, what time am I free before calling my parents on july 20, 2025 according to my calendar? Give me the title of the article.

MCP-Atlas task `689af4e653c3905e7b5b259c`.

## The surface

Atlas enables 13 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| pubmed | 4 | `pubmed`, the MCP arm's own server |
| memory | 3 | `memory`, the MCP arm's own server |
| google-workspace | 1 | `/calendar`, a read-only mount, and `google-workspace`, the MCP arm's own server, on the Calendar fake |
| filesystem | 5 | `/data`, a disk mount |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

The calendar is not live. Atlas has a user import its `.ics` into a fresh
Google account; both arms here read mirage's Google Workspace fake, seeded per
run from the same export by `server/seed/atlas_exports.py` -- Google's own
event ids, the two weekly series expanded into the instances Google lists, in
the New York zone the recordings read -- and googleapis.com is answered by
`server/fakes/slack_host.py`. All 22 recorded `list_events` calls replay byte
for byte.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/k12-education-free-time --tools vfs
    uv run python agent/run_agent.py mcpatlas/k12-education-free-time --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py k12-education-free-time
