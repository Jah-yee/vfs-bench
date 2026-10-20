# Snake repo commit count

> I need to find a repository on my computer, I don't remember the exact name of the folder, but I know it includes something about snake. Can you tell me what it's named and how many commits were made in this folder from June 2022 to July 15, 2023?

MCP-Atlas task `689bd255c0422b257e7dfcfd`.

## The surface

Atlas enables 15 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| git | 1 | `git`, on the same clones |
| filesystem | 10 | `/data`, a disk mount |
| github | 3 | `gh`, live |
| whois | 1 | `whois`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/snake-repo-commit-count --tools vfs
    uv run python agent/run_agent.py mcpatlas/snake-repo-commit-count --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py snake-repo-commit-count

Both arms need `GITHUB_TOKEN` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
