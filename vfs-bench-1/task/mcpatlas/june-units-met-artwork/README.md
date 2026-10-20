# June units met artwork

> I want to get the total units sold on june in the year 2022 in our car dealership, then use that number as an ID to search the metropolitan museum of art collection for the artwork with that exact id and provide its official title and the department.

MCP-Atlas task `68940d8355faa0b720f0b478`.

## The surface

Atlas enables 16 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| airtable | 3 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| met-museum | 3 | `met-museum`, the MCP arm's own server |
| github | 5 | `gh`, on the GitHub fake |
| git | 5 | `git`, on the same clones |

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
    uv run python agent/run_agent.py mcpatlas/june-units-met-artwork --tools vfs
    uv run python agent/run_agent.py mcpatlas/june-units-met-artwork --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py june-units-met-artwork
