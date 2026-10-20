# Colombia road trip distance

> I'm planning a road trip in colombia following key historical places. From plaza de bolivar, bogotá, the route must go through plaza de la audana, cartagena, and end at the boyacá bridge where the battle of boyacá took place. Provide me the total distance that the trip would take in meters, and give me the date of that battle and the date when the colombian war of independence started.

MCP-Atlas task `688fb11183792b921381bd66`.

## The surface

Atlas enables 14 tools from seven servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| wikipedia | 3 | `wikipedia`, the MCP arm's own server |
| osm-mcp-server | 3 | `osm-mcp-server`, the MCP arm's own server |
| weather | 3 | `weather`, the MCP arm's own server |
| context7 | 2 | `context7`, the MCP arm's own server |
| github | 1 | `gh`, on the GitHub fake |
| git | 1 | `git`, on the same clones |
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts only its repositories, from a copy taken out of the same
image, at the same paths: this task's tools read `/data` through git alone.
Every server runs in that image, started as upstream's app starts it, and its
`tools/list` is the image's; the divergences are declared on each builder in
`task/mcpatlas/__init__.py`.

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
    uv run python agent/run_agent.py mcpatlas/colombia-road-trip-distance --tools vfs
    uv run python agent/run_agent.py mcpatlas/colombia-road-trip-distance --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py colombia-road-trip-distance

Both arms need `E2B_API_KEY` (see `.env.example`) for the live services Atlas
enables, the same on both arms.
