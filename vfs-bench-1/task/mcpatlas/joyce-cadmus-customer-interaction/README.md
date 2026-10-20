# Joyce cadmus customer interaction

> My boss uses a weird mnemomic device to remember dates and he asked me to review the cluod database and check the interactions on the same day and month that james joyce, the author of ulysses 1922, was born, but in the year when the author of the marriage of cadmus and harmony passed away. He wants to know who the customer was, what kind of feedback they gave, detalis about the vehicle they mentioned, who handled the case, and how the interaction was carried out.

MCP-Atlas task `68952adeba1c2ad4e6a5db36`.

## The surface

Atlas enables 15 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| pubmed | 2 | `pubmed`, the MCP arm's own server |
| git | 4 | `git`, on the same clones |
| airtable | 5 | `/airtable`, a read-only mount, and `airtable`, the MCP arm's own server, on the Airtable fake |
| open-library | 4 | `open-library`, the MCP arm's own server |

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

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/joyce-cadmus-customer-interaction --tools vfs
    uv run python agent/run_agent.py mcpatlas/joyce-cadmus-customer-interaction --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py joyce-cadmus-customer-interaction
