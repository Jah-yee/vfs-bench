# Zhang health speaker name

> I will need to speak with a public health speaker from the zhang family. I'm sure i have his full name on my notes but i can't remember it for sure. I'll need that so i don't embarrass myself. We will be discussing the world health organization, and i also really need to know when it was founded becuase we are meeting on the anniversary on 2025, can you tell me if I have the date added to my calendar?

MCP-Atlas task `68a398aa2f58036e8d45eddc`.

## The surface

Atlas enables 13 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| cli-mcp-server | 2 | the shell itself, over `/data` |
| google-workspace | 1 | `/calendar`, a read-only mount, and `google-workspace`, the MCP arm's own server, on the Calendar fake |
| memory | 3 | `memory`, the MCP arm's own server |
| wikipedia | 7 | `wikipedia`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/zhang-health-speaker-name --tools vfs
    uv run python agent/run_agent.py mcpatlas/zhang-health-speaker-name --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py zhang-health-speaker-name
