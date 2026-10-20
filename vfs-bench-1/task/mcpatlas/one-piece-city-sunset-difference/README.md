# One piece city sunset difference

> I am a big anime fan and live in the same city where the creator of one piece was born. i am curious to know in my city on which of these two days the sunset occurred earlier and how many minutes of difference there were between the day the first episode of the one piece anime aired and the day the first episode of the dragon ball anime aired.

MCP-Atlas task `689e0b1d9c8e2ac413c1f245`.

## The surface

Atlas enables 15 tools from six servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| oxylabs | 1 | `oxylabs`, the MCP arm's own server |
| mcp-code-executor | 1 | `python3`, pyodide |
| weather-data | 3 | `weather-data`, the MCP arm's own server |
| weather | 1 | `weather`, the MCP arm's own server |
| git | 6 | `git`, on the same clones |
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
    uv run python agent/run_agent.py mcpatlas/one-piece-city-sunset-difference --tools vfs
    uv run python agent/run_agent.py mcpatlas/one-piece-city-sunset-difference --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py one-piece-city-sunset-difference

Both arms need `OXYLABS_USERNAME`, `OXYLABS_PASSWORD` and `WEATHER_API_KEY`
(see `.env.example`) for the live services Atlas enables, the same on both
arms.
