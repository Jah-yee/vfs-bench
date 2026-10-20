# Cookie-day genre article

> Based on my database inventory, could you calculate the average stock for each game genre for august 2023, rounded to two decimal places? Then, for my research, pick the genre with the highest stock and fin an article about it published on the same day I'm planning to bake cookies with my mom over facetime in july 2025, written by rushia harada. What's the title of that article?

MCP-Atlas task `689a373e148a49f91233e016`.

Role-Playing has the highest average stock in August 2023's `Inventory`
documents, 159.00. "Bake Cookies with Mom (FaceTime)" is at 20:00 on
2025-07-15, New York time, and Rushia Harada's arXiv paper of that day is
"Role-Playing LLM-Based Multi-Agent Support Framework for Detecting and
Addressing Family Communication Bias".

## The surface

Atlas enables 14 tools from four servers; the mirage arm has one shell tool.

| server | tools enabled | on the mirage arm |
|---|---:|---|
| mongodb | 9 | `/mongodb`, a read-only mount, and `mongodb`, the MCP arm's own server, on the run's MongoDB |
| memory | 3 | `memory`, the MCP arm's own server |
| arxiv | 1 | `arxiv`, the MCP arm's own server |
| google-workspace | 1 | `/calendar`, a read-only mount, and `google-workspace`, the MCP arm's own server, on the Calendar fake |

## What is upstream's and what is ours

The ask, the enabled tools and the claims are the dataset row, verbatim, in
`shared/task.md` and `shared/atlas.json`, traced by `dvc.yaml`'s `atlas-task`
stage. Every server runs in a container of `ghcr.io/scaleapi/mcp-atlas:1.2.7`
started per run, started as upstream's app starts it, and its `tools/list` is
the image's; the divergences are declared on each builder in
`task/mcpatlas/__init__.py`.

MongoDB is not Atlas's cluster. Atlas has a user restore its
`video_game_store` dump into a cluster of their own; both arms here read a
MongoDB started per run and restored from the same dump by
`server/seed/atlas_exports.py`, with each collection's UUID kept, and the MCP
arm's server reaches it on the connection string the template reads. It is
MongoDB 7.0 where an Atlas cluster runs 8.0, because every 8.0 build refuses
Docker Desktop's kernel (SERVER-121912). Replayed through the server, the
recorded calls come back the same but for what a standalone server cannot
match: `list-databases`' sizes and its `config` database, and the first page
an unsorted `find` or `$group` returns, which the recorded cluster did not
keep stable between its own recordings either.

The calendar is not live. Atlas has a user import its `.ics` into a fresh
Google account; both arms here read mirage's Google Workspace fake, seeded per
run from the same export by `server/seed/atlas_exports.py` -- Google's own
event ids, the two weekly series expanded into the instances Google lists, in
the New York zone the recordings read -- and googleapis.com is answered by
`server/fakes/slack_host.py`. All 22 recorded `list_events` calls replay byte
for byte.

Ours: the mirage arm's `vfs/` prompt. The grade is upstream's own scorer and
judge's, as the dataset README describes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/cookie-day-genre-article --tools vfs
    uv run python agent/run_agent.py mcpatlas/cookie-day-genre-article --tools mcp
    BENCH_DATASET=mcpatlas uv run python tests/parity.py cookie-day-genre-article
