# server/clients/

The client side of every fake, and the only implementation of each. These
are what *both* arms call: the mirage arm's CLIs import them by name, and
upstream's MCP servers and evaluators reach the same modules through
[`redirect/`](../../redirect/README.md), which shadows the name each one is
normally imported under.

| module | stands in for | on | called by |
|---|---|---|---|
| `snowflake.py` | a Snowflake warehouse | Postgres, one database per Snowflake database | the MCP arm's server, which both arms run, three evaluators, three seeders |
| `cloud_logging.py` | Google Cloud Logging | HTTP, on the fixture API | the MCP arm's server, which both arms run, evaluators, `seed_logging.py` |
| `gws.py` | Drive and Sheets | HTTP, on mirage's mock | seeders, verifiers |
| `notion.py` | the Notion REST API | HTTP, on mirage's mock | the same |

They are here rather than in a directory of their own because a fake is not
a thing this repo serves — Postgres, the fixture API and mirage's mocks
serve; these are how the two surfaces *reach* them. Nothing here knows it is
a substitute: the deception is entirely `redirect/`'s.

Yahoo Finance is not faked. Upstream reads it live on every task, and so
do both arms here: the CLI, the MCP server and upstream's evaluators all
call the original SDK, through the one recording transport in
[`server/seed/public_services.py`](../seed/public_services.py), and nothing
a run reads is kept.

## The fixture Postgres stands in for Snowflake

Four Toolathlon tasks — `sla-timeout-monitor`, `payable-invoice-checker`,
`landing-task-reminder`, `travel-expense-reimbursement` — reach a live
Snowflake warehouse through a private key. That is a paid service, the
fixture would live in somebody's cloud account, and all four tasks *write*
to it, so a graded run could neither be reproduced nor rolled back.

[`snowflake.py`](snowflake.py) is the substitute: one Postgres
database per Snowflake database, in the fixture cluster, and a dialect layer thin
enough to list. [`redirect/snowflake/`](../../redirect/snowflake/) shadows both
faces of the real client on top of it, so one `PYTHONPATH` entry redirects
everything at once:

| face | who imports it | what it is |
|---|---|---|
| `snowflake.snowpark.Session` | the MCP server's `db_client.py` | `sql()` / `collect()` / `asDict()` |
| `snowflake.connector` | Toolathlon's `utils/app_specific/snowflake/client.py`, used by three evaluators | `connect()`, `DictCursor` |

Both arms therefore agree on which SQL is legal, because both go through
one rewriter. A dialect gap is a property of the fixture, paid by both,
rather than an advantage handed to one.

`snowflake.py`'s docstring is the list of eleven rewrite rules, and each is
one the four tasks actually depend on. Anything not on it reaches Postgres
as written and fails with Postgres's own message, which beats a rewrite
nobody can see.

```bash
uv run python server/mcp/setup_snowflake.py    # the pinned fork, no cloud client
```

Each rule above is one the four tasks actually depend on, and the module's
own docstring is the list. The comment round trip is the one to keep an eye
on: `payable-invoice-checker` is scored on a column description, so a
rewrite that dropped it would grade red for a reason that is ours, not the
model's.

Each of the four tasks brings its own database, seeded by its own
`task/toolathlon/<task>/shared/seed_db.py` rather than from a file in `fixtures/`.
That is not a stylistic choice: these fixtures are placed relative to a
clock — `created_at = now - 40 hours` — so what counts as overdue depends
on when the rows were written, and the ground truth has to be emitted by
the same pass that writes them. `server/seed/seed_task.py` runs the seeder once
per arm, and the ground truth it writes beside the task wins over
upstream's committed copy. The DDL is upstream's own, run through the fake
rather than hand-translated, so seeding is itself a test that the rewriter
handles what these tasks write.

Where upstream's preprocess can be run rather than copied, it is:
`landing-task-reminder` needs only the `PYTHONPATH`,
`payable-invoice-checker` swaps one thin MCP layer for direct calls. Only
`sla-timeout-monitor` is reproduced, because its fixture is computed from
the clock at seeding time.

mirage also has a native `postgres` resource, which mounts a database as
`<schema>/tables/<table>/{schema,semantic,rows}.jsonl` and pushes `grep`,
`head`, `tail` and `wc` down into SQL. It is read-only, so a task that
writes mounts it for reading and keeps the `sql` CLI for the rest.
