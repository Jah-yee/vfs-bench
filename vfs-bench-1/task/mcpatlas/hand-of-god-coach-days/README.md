# Hand of god coach days

> I've been diving into that infamous hand of god moment and want to know who was coaching the side that took the lead with that goal, which ended up winning the tournament that year. I'm also trying to work out how many days elapsed between him lifting the trophy and his final match at the world cup, and, while I'm at it, could you give me the latitude and longitude of the stadium where they clinched the title?

MCP-Atlas task `6890e7fd2516f66b0a628e7c`.

## The surface

Atlas enables 15 tools from nine servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| e2b-server | 1 | `e2b-server`, the MCP arm's own server |
| exa | 1 | `exa`, the MCP arm's own server |
| wikipedia | 2 | `wikipedia`, the MCP arm's own server |
| google-maps | 1 | `google-maps`, the MCP arm's own server |
| airtable | 2 | `airtable`, the MCP arm's own server, on the Airtable fake |
| desktop-commander | 1 | `/data`, a disk mount |
| github | 2 | `gh`, on the GitHub fake |
| national-parks | 2 | `national-parks`, the MCP arm's own server |
| weather-data | 3 | `weather-data`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run, and
the mirage arm mounts a copy of it taken out of the same image, so both read
the same bytes at the same path. Every server runs in that image, started as
upstream's app starts it, and its `tools/list` is the image's; the divergences
are declared on each builder in `task/mcpatlas/__init__.py`.

Airtable is not live. Atlas ships its base as a share link a user copies into
an account of their own; both arms here read mirage's fake of the service,
seeded per run with the base as mirage captured it from that link,
`integ/truth/airtable_atlas.json` at the `submodule/mirage` gitlink, which
mirage replays Atlas's recorded Airtable calls against. Upstream's server takes
no base URL, so it reaches the fake through a proxy and a CA of this repo's,
`server/fakes/slack_host.py`.

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
    uv run python agent/run_agent.py mcpatlas/hand-of-god-coach-days --tools vfs
    uv run python agent/run_agent.py mcpatlas/hand-of-god-coach-days --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py hand-of-god-coach-days

Both arms need `E2B_API_KEY`, `EXA_API_KEY`, `GOOGLE_MAPS_API_KEY`,
`NPS_API_KEY` and `WEATHER_API_KEY` (see `.env.example`) for the live services
Atlas enables, the same on both arms.
