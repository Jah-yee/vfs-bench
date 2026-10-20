# Mustang claim customer details

> I was checking the cloud data repository and I noticed that a customer whose car is a mustang left a claim in august 7 2017, I would like you to retrieve the information of the person who left this claim I want to know the persons id and the car year and I also remember that the service rating is the same as my favorite department in the metropolitn museum of art, retrieve the name of the department which matches the service rating

MCP-Atlas task `68940d8355faa0b720f0b482`.

## The surface

Atlas enables 15 tools from five servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| airtable | 5 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| cli-mcp-server | 1 | the shell itself, over `/data` |
| weather | 2 | `weather`, the MCP arm's own server |
| met-museum | 3 | `met-museum`, the MCP arm's own server |
| pubmed | 4 | `pubmed`, the MCP arm's own server |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. The fixture is Atlas's `/data`: the MCP arm's servers read the image's
own, in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7` started per run. The
mirage arm mounts none of it, because none of this task's tools reads it.
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

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/mustang-claim-customer-details --tools vfs
    uv run python agent/run_agent.py mcpatlas/mustang-claim-customer-details --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py mustang-claim-customer-details
