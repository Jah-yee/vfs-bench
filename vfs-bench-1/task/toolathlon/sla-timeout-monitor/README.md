# SLA timeout monitor

Find the support tickets that blew their first-reply deadline, mail every
affected customer an apology, and mail each of their account managers one
reminder listing their overdue tickets. The deadlines and both email
templates are in a handbook — one of ten PDFs in a tarball, and not the
only one that looks like an SLA.

## The handbook is a trap in three ways

The tarball holds ten PDFs. Nine are ordinary company documents; two look
like the SLA. `slamanual.pdf` is stamped **OBSOLETE** and states response
times by incident priority (P1 30 min, P2 2 hours) — used by mistake it
produces a completely different answer. `sla_manual.pdf` is the live
handbook, and it needs three repairs before its templates can be quoted:

- **The `fi` ligature is gone.** Both extractors emit U+0000 where it was,
  so the manager template reads "the SLA ␀rst reply time". The grader
  compares bodies after `re.sub(r'[^\w]', '', s).lower()`, so an unrepaired
  copy fails on one word. This is not an arm difference: `pdf-tools-mcp`
  uses PyPDF2 and the mirage arm uses pypdf, and the two produce the same
  hole.
- **The page footer falls inside the template**, one line below "Dear
  Manager,". A body with "Page 4 of 5" in it does not match.
- **So does an instruction to the sender** — "Within the same service
  level, please order by creation time in chronological order" — which is
  the only place the tie-break is stated, and is guidance rather than text
  to quote.

## Which clock

Every ticket is placed relative to a clock — `created_at = now - 40 hours`
— so "overdue" is a question about *whose* now. The fixture container runs
`Etc/UTC` and the machine running the agent generally does not, which puts
`date` and `SELECT CURRENT_TIMESTAMP` seven hours apart here.

`shared/seed_db.py` anchors the rows to the warehouse's clock, which is what
upstream's preprocess does and the only choice that makes the ages mean
anything. Both arms then have the same question in front of them and the
same two ways to answer it, one of which is to ask the database:

```sql
SELECT ... FROM SLA_MONITOR.public.support_tickets t
JOIN SLA_MONITOR.public.users u ON u.id = t.user_id
WHERE t.first_response_at IS NULL
  AND CURRENT_TIMESTAMP > t.created_at + CASE u.service_level ... END
```

An earlier draft of the seeder used the host clock instead. That was the
fixture's fault, and it is fixed.

## No warehouse, and no `/db`

Toolathlon points its snowflake server at a paid Snowflake account. This
repo runs the same server — the fourteen-tool fork its config names, not
the eight-tool PyPI package it actually launches — over the fixture
Postgres, by shadowing `snowflake.snowpark` and `snowflake.connector`. The
mirage arm reaches the same rows through the `snowflake` CLI, which runs
that same server, so a dialect gap is paid by both arms rather than handed to one.
See [server/clients/README.md](../../../server/clients/README.md).

`snowflake` is a CLI and not a mount, deliberately. mirage has a native
`postgres` resource that renders a database as a directory tree, but a
warehouse is not path-shaped: a table is a query, and no listing an agent
could `ls` returns a row. The tools upstream's server exposes for reading
and writing are the whole surface here too.

## The fixture

[`shared/seed_db.py`](shared/seed_db.py) replaces upstream's
`preprocess/create_snowflake_db.py`, which builds the same database over
MCP against the live account. It reproduces upstream's generator exactly —
the same fifteen users, the same ticket corpus, `random.seed(42)`, and the
same order of `random` calls — and upstream's own committed
`groundtruth_workspace/sla_monitoring.jsonl` is the check on it: all
fifteen rows agree on ticket number, service level, manager and
`is_overdue`, and differ only in the timestamps, which is exactly what
moving the clock should change.

The DDL is upstream's, run through the shim rather than hand-translated to
Postgres, so every seed is also a test that the rewriter still handles
`AUTOINCREMENT`, `CURRENT_TIMESTAMP()` and three-part names.
