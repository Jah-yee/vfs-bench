# Payable invoice checker

Fifteen supplier invoices have arrived as PDFs, in six different layouts.
Put every one of them into the two warehouse tables, mail each purchasing
manager the filenames they still have to chase, and label the
`outstanding_flag` column so the next person knows which way round it
reads.

## What actually decides the answer

Nine of the fifteen invoices print a payment line — `PAYMENT STATUS: ✓
PAID`, `■ PARTIAL ($41064.28 of $108909.36)`, `✗ UNPAID`. The other six
print a phrase instead:

```
Payment under review        Processing for payment
Pending payment approval    Awaiting payment authorization
Payment verification in process
```

and no figure at all. Upstream's ground truth marks **two of those six
outstanding**, so an agent that reads silence as settled misses
`BL-2024-400.pdf` and `INV-2024-014.pdf` and fails. The warehouse cannot
break the tie either: none of the fifteen is in it yet, which is the thing
being fixed. Treating an invoice as paid only where the document says so is
the only rule that passes.

Extra caution is free here: the grader checks that each manager with an
outstanding invoice got one email naming all of theirs, and does not mind
being told about invoices that turned out to be paid.

## The mailbox needed folders, and one check only binds one arm

Two things came out of this task that are worth writing down.

**GreenMail gives a new mailbox an `INBOX` and nothing else.** poste.io,
which Toolathlon runs, creates `Sent`, `Drafts` and `Trash` with the
account. This evaluator opens the sender's `Sent` to check nobody mailed
the thousand interference buyers, and against GreenMail that is not a
failed check but a crashed one — `SELECT failed. No such mailbox` — which
marks the run wrong whatever the agent did. [`server/seed/mail_folders.py`](../../../server/seed/mail_folders.py)
creates the folders from the account list each task already ships, and
`task.json` orders it after the mail reset.

**With the folders there, the check binds the MCP arm only.** `emails-mcp`
appends every send to `Sent`, so its messages are there to be
examined; mirage's `himalaya ... --send` is SMTP and nothing else, with no
IMAP copy and no config for one, so its `Sent` is empty by construction.
Real himalaya does copy. It is an asymmetry in strictness rather than in
cost, and the fix belongs in mirage.

## No warehouse, and upstream's own seeder again

Toolathlon points its snowflake server at a paid account. This repo runs
the same server over the fixture Postgres by shadowing
`snowflake.snowpark` and `snowflake.connector`; the mirage arm reaches the
same rows through the `snowflake` CLI, which runs that same server. See
[server/clients/README.md](../../../server/clients/README.md).

This preprocess drives the MCP server, the way
[sla-timeout-monitor](../sla-timeout-monitor/README.md)'s does and
[landing-task-reminder](../landing-task-reminder/README.md)'s does not, so
`PYTHONPATH` alone is not enough. It is still not reimplemented. Five MCP
tools are reached — `create_databases`, `drop_databases`, `create_table`,
`write_query`, `read_query` — and every one is a thin wrapper over a
statement the shim already answers, so [`shared/seed_db.py`](shared/seed_db.py)
replaces just that layer and lets upstream's own script draw the thousand
interference rows, render the fifteen PDFs and write its own ground truth.

The check on that is exact: running it rewrites upstream's committed
`invoice.jsonl`, `interference_invoices.jsonl` and
`interference_payments.jsonl` in place, and `git status` in the Toolathlon
checkout comes back clean. The fixture this repo builds is upstream's
fixture, byte for byte.

One dialect rule was added for this task, the eleventh: Snowflake sets a
column comment with `ALTER TABLE t MODIFY COLUMN c COMMENT '...'`, which
Postgres spells `COMMENT ON COLUMN t.c IS '...'`. Both dialects accept the
second, either arm might write the first, and the comment is graded.
