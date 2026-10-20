# The storyteller's creator and first commit

> I am testing out a program and want to know about the creator. The program is on my local pc and can be used to tell stories. Tell me when the first commit was on this repo. Tell me what the creator's username according to the hosting platform along with their first and last name

MCP-Atlas task `689f4d693e212e8ef339073a`.

The program is `/data/repos/storyteller`, whose first commit, on 2023-09-11, is
Lars Grammel's; on GitHub he is `lgrammel`.

## The surface

Atlas enables 15 tools from six servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| memory | 3 | `memory`, the MCP arm's own server |
| filesystem | 3 | `/data`, a disk mount |
| github | 1 | `gh`, live |
| git | 1 | `git`, on the same clones |
| notion | 4 | `/notion`, a read-only mount, and `notion`, the MCP arm's own server, on the Notion fake |
| met-museum | 3 | `met-museum`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

Notion is not live. Atlas reads a workspace a user imports from its own export;
both arms here read mirage's fake of the service, seeded per run from that
export by `server/seed/atlas_exports.py`, and the MCP arm's server is pointed
at it through settings the server itself takes. The Notion rows keep the ids
and schemas Atlas's recordings carry.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/storyteller-creator-first-commit --tools vfs
    uv run python agent/run_agent.py mcpatlas/storyteller-creator-first-commit --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py storyteller-creator-first-commit

Both arms need `GITHUB_TOKEN` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
