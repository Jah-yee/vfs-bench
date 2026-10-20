# Serpent repo first pr branch

> I cloned a repo game locally to my laptop about serpents but haven't looked at the main repo since. Can you check what branch was used in the very first pull request opened there?

MCP-Atlas task `689f4d693e212e8ef3390737`.

## The surface

Atlas enables 20 tools from three servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| cli-mcp-server | 2 | the shell itself, over `/data` |
| git | 6 | `git`, on the same clones |
| github | 12 | `gh`, live |

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
    uv run python agent/run_agent.py mcpatlas/serpent-repo-first-pr-branch --tools vfs
    uv run python agent/run_agent.py mcpatlas/serpent-repo-first-pr-branch --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py serpent-repo-first-pr-branch

Both arms need `GITHUB_TOKEN` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
