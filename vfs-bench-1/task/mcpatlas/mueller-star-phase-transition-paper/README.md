# Mueller star phase transition paper

> I'm on my 2025 summer break and feel like diving into some papers. Earlier this year, my old teacher bernhard mueller at monash did some 3d sims about the formation of a certain type of star. I'm more into the dynamical phase transition for those stars. If we look back before 2018, what's the most recent paper about the topic I am interested in?

MCP-Atlas task `689a373e148a49f91233e029`.

## The surface

Atlas enables 13 tools from six servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| oxylabs | 3 | `oxylabs`, the MCP arm's own server |
| arxiv | 1 | `arxiv`, the MCP arm's own server |
| fetch | 1 | `fetch`, the MCP arm's own server |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| filesystem | 4 | `/data`, a disk mount |
| github | 3 | `gh`, on the GitHub fake |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

GitHub is not live. This task's row asks about nothing on GitHub, and live
GitHub answers whatever the token reaches, private repositories included, so
both arms here read mirage's GitHub fake, started per run and holding nothing:
a search finds nothing and a repository is not found, as GitHub answers for
what it does not hold. The MCP arm's server takes no base URL, so
`redirect/github/github_hook.mjs` moves api.github.com inside its `fetch`; `gh`
is given the fake's URL.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/mueller-star-phase-transition-paper --tools vfs
    uv run python agent/run_agent.py mcpatlas/mueller-star-phase-transition-paper --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py mueller-star-phase-transition-paper

Both arms need `OXYLABS_USERNAME`, `OXYLABS_PASSWORD` and `E2B_API_KEY` (see
`.env.example`) for the live services Atlas enables, the same on both arms.
