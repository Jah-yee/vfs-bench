# Italian settler cohan distance

> I heard about the monument in honor of the first Italian settler in new york state, and I became curious about it. There's also the george m. cohan statue in the same city, what is the driving distance in meters between these two monuments?

MCP-Atlas task `6897a6002b64a8c831efa2e9`.

## The surface

Atlas enables 18 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| git | 4 | `git`, on the same clones |
| github | 6 | `gh`, on the GitHub fake |
| ddg-search | 2 | `ddg-search`, the MCP arm's own server |
| google-maps | 5 | `google-maps`, the MCP arm's own server |
| mcp-code-executor | 1 | `python3`, pyodide |

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
    uv run python agent/run_agent.py mcpatlas/italian-settler-cohan-distance --tools vfs
    uv run python agent/run_agent.py mcpatlas/italian-settler-cohan-distance --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py italian-settler-cohan-distance

Both arms need `GOOGLE_MAPS_API_KEY` (see `.env.example`) for the live services
Atlas enables, the same on both arms.
