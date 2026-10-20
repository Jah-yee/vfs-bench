# Maldoff paper lowest salary

> My colleague gabe maldoff published a paper on web scraping ethics. In the same month and year as its publication, what was the lowest salary among the players whose contracts expired in that same month and year, according to my fantasy sports archive?

MCP-Atlas task `689f4d693e212e8ef3390736`.

## The surface

Atlas enables 16 tools from eight servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| arxiv | 1 | `arxiv`, the MCP arm's own server |
| memory | 3 | `memory`, the MCP arm's own server |
| pubmed | 4 | `pubmed`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |
| filesystem | 3 | `/data`, a disk mount |
| context7 | 2 | `context7`, the MCP arm's own server |
| github | 1 | `gh`, on the GitHub fake |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |

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
    uv run python agent/run_agent.py mcpatlas/maldoff-paper-lowest-salary --tools vfs
    uv run python agent/run_agent.py mcpatlas/maldoff-paper-lowest-salary --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py maldoff-paper-lowest-salary

Both arms need `E2B_API_KEY` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
