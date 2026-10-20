# Animal business sarmiento week

> I remember recording my earnings of my business focused on animal well-being on the year tina turner died. Could you help me find the net earnings for the seven day period in that year including the day when domingo faustino sarmiento was born.

MCP-Atlas task `68993ef3cf3e953b8ab83fca`.

## The surface

Atlas enables 14 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| ddg-search | 2 | `ddg-search`, the MCP arm's own server |
| filesystem | 4 | `/data`, a disk mount |
| git | 3 | `git`, on the same clones |
| github | 3 | `gh`, on the GitHub fake |
| mcp-code-executor | 2 | `python3`, pyodide |

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
    uv run python agent/run_agent.py mcpatlas/animal-business-sarmiento-week --tools vfs
    uv run python agent/run_agent.py mcpatlas/animal-business-sarmiento-week --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py animal-business-sarmiento-week
