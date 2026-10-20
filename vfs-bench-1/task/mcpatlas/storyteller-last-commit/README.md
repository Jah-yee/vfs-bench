# Storyteller last commit

> Which files were touched in the storyteller project in the last update of 2024, who did it and what they described?

MCP-Atlas task `689a373e148a49f91233dfdc`.

`/data/repos/storyteller` is a real clone at upstream's commit. Its last
2024 commit is `0865ef4`, Lars Grammel, 2024-04-03 15:39:04 +0200, "Merge
pull request #1 from pH-7/patch-1 / Update incorrect filename link", and it
touches `README.md` only.

## The surface

Atlas enables 15 tools from 4 servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| desktop-commander | 4 | `/data`, a disk mount |
| git | 2 | `git`, Mirage's, over the same clone |
| mcp-code-executor | 2 | `python3`, pyodide |
| github | 7 | `gh`, live |

## desktop-commander is handed over as upstream hands it

Upstream's sandbox calls `set_config_value allowedDirectories ["/data"]` the
moment the server is up, and `get_config` -- which this task enables --
reports that call and that session back. So the builder makes the call, in a
session of its own, in the run's container; the arm's session is the server's
second, as upstream's is. The directory is `/data` and `systemInfo` is the
image's; the `clientId` is fresh, as it is in every upstream sandbox.

## Upstream's git server misreads its own log

`git_log` with a timestamp formats five lines per commit and reads them four
at a time, so every record after the first is shifted. It is the image's
version and so Atlas's reply too.

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/storyteller-last-commit --tools vfs
    uv run python agent/run_agent.py mcpatlas/storyteller-last-commit --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py storyteller-last-commit

Both arms need `GITHUB_TOKEN` (see `.env.example`); GitHub is live on both,
on the same token.
