# Landing task reminder

Three people start today. Give each of them the training tasks their group
gets, with the deadlines the onboarding handbook sets, write those tasks
into the warehouse, and mail each new hire their list. Then find everyone
whose deadline has already passed with the task still open, and mail them
too — copying each person's supervisor.

## The PDF extractor

`pdf-tools-mcp` — which upstream pins, and which this repo runs unmodified
— reads PDFs with **PyPDF2**, long unmaintained. On this document PyPDF2
emits a NUL byte before every single character:

```
PyPDF2:  6,758 chars, 3,285 NULs   '\x00C\x00o\x00m\x00p\x00a\x00n\x00y…'
pypdf:   3,450 chars,     0 NULs   'Company Unified Onboarding Checklist…'
```

Every NUL becomes a six-character escape once the result is JSON-encoded
for the wire, so three pages of a plain checklist arrive as **23,742
characters, about 13,500 tokens**.

For contrast, [sla-timeout-monitor](../sla-timeout-monitor/README.md) uses
the same two libraries on a different PDF and they agree exactly, down to
dropping the same `fi` ligature. Which library you get only matters when
the font does.

## Where the group comes from

The `EMPLOYEE` table has `employee_id`, `name`, `email` and `report_to_id`.
It does **not** have a group. A new hire has no tasks yet, so no
`GROUP_TASKS_*` table names them either, and nothing in the workspace maps
a person to a team.

What places them is their manager. `report_to_id` points at one of four
managers; each manager carries their own group's default tasks; so the
group table that contains the manager is the group the new hire joins. Both
arms have to find that chain.

## No warehouse, and upstream's own seeder

Toolathlon points its snowflake server at a paid account. This repo runs
the same server over the fixture Postgres by shadowing
`snowflake.snowpark` and `snowflake.connector`; the mirage arm reaches the
same rows through the `snowflake` CLI, which runs that same server. See
[server/clients/README.md](../../../server/clients/README.md).

What is different here from
[sla-timeout-monitor](../sla-timeout-monitor/README.md) is the seeder.
That task's preprocess drives the MCP server, so it had to be reproduced.
This one talks to `utils/app_specific/snowflake/client.py` — which the shim
already shadows — so [`shared/seed_db.py`](shared/seed_db.py) is a dozen
lines that put `redirect/snowflake` on `PYTHONPATH` and run **upstream's own
preprocess**, building all seven tables from upstream's own committed
`landing_task.json`. Nothing to drift.

Getting there cost five dialect rules, each found by running the real thing
rather than guessing: a session on the account-metadata `SNOWFLAKE`
database, `CREATE DATABASE IF NOT EXISTS`, `CREATE SCHEMA db.schema`, the
column label Snowflake gives a bare `SELECT CURRENT_TIMESTAMP()`, and a
fully quoted `"DB"."SCHEMA"."TABLE"` — the last a router gap left over from
the previous task, where only the schema and table parts could be quoted.

## Which clock

Upstream anchors both halves to the warehouse: its preprocess reads
`CURRENT_TIMESTAMP()` and places every date against it, and its evaluator
reads the same clock again at grading time, ignoring the `--launch_time`
its own parser demands. So the hazard
[sla-timeout-monitor](../sla-timeout-monitor/README.md) had to be fixed for
is already handled here by upstream's own design — provided seeding and
grading fall on the same calendar day, since the expected `create_date` is
the grading date.
