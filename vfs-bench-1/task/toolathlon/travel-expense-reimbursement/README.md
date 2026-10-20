# Travel expense reimbursement

Sixteen expense claims arrive as `.tar.gz` packages, each holding a claim
form and one PDF invoice per line item. Check every claim for complete
invoices and matching amounts; mail the employee and copy their manager
about the ones that fail; write the rest into the Snowflake
`2024Q4REIMBURSEMENT` table, flagging the ones over policy caps and mailing
about those too.

`EXP2024015` is a three-night L1 trip to Stockholm whose meals on
2024-10-07 come to CNY 840 against a CNY 600 daily cap — except that the
invoice for it carries `Client Entertainment: Yes` and
`Manager Pre-Approval: Yes`, and the policy's
`client_entertainment_exception` multiplies the meal cap by 1.5 for exactly
that case. 840 is under 900, the claim is compliant, and `FLAG` is 0.

## The port defect mirage could not be graded without

The evaluator reads the **sender's `Sent` folder** — `find_sent_emails`
selects it over IMAP and matches subject, `To` and `Cc`. Toolathlon's
`emails-mcp` appends every message it sends there (`save_to_sent`, trying
`Sent`, `INBOX.Sent`, `Sent Messages`, `Sent Items`). mirage's `himalaya`
handed the message to SMTP and kept no copy, so the mirage arm's `Sent` was
empty however many correct emails it sent, and no draw of it could have
passed.

So `himalaya message ... --send` now files the delivered bytes in the sent
folder, in both languages, probing the same four names. It is the delivered
form, Bcc already stripped, which is what a copy of a sent message has to
be. That is mirage `47cd1a9`, and this pin bump.

Verified three ways: `/mail/Sent` shows the message after a send,
Toolathlon's own `find_sent_emails` reads back the right subject, `To` and
`Cc`, and a golden solver took the whole task
through the mirage surface, with the evaluator answering `[PASS] All
expected emails exist and no extra emails found`.

That is why the email half is known to work. The solver read the answer out of the ground truth rather
than deriving it — the derivation is upstream's generator, which seeding
already runs — and spends its effort on the two things that could actually
be wrong about the port: whether `snowflake` can write a table whose name starts
with a digit, and whether a `himalaya` message lands where the grader looks.

## What the port is made of

`shared/seed_db.py` runs **upstream's own preprocess**. Three of its four
steps needed nothing: it clears twelve mailboxes over IMAP, generates the
claims and their ground truth from `random.Random(7)`, and renders the
policy PDF and sixteen claim packages with reportlab. Only step 3 drives the
Snowflake MCP server, which will not start without
`snowflake_private_key_path`, and the preprocess hung there for 120 seconds
and then died.

There is one data-generation correction. Upstream passes its fixed seed 7 to
claim generation, but contact phone numbers use the separate module-level
`random` generator and therefore differ between runs. The wrapper replaces
only that module reference with an isolated `random.Random(7)`. The upstream
contact generator, call order, and employee/manager number ranges remain
unchanged, while both arms now receive the same phone values.

`task/toolathlon/shared/snowflake_mcp.py` replaces that tool layer and nothing else —
five tools, each a thin wrapper over a statement `redirect/snowflake` already
answers — which is what
[payable-invoice-checker](../payable-invoice-checker/README.md) does, and
why the stand-in now lives in `shared/` rather than in one task's seeder.

The one difference between the two is worth naming, because it cost a debug
cycle: payable-invoice-checker's preprocess writes `from . import
create_snowflake_db`, so patching the package-qualified module reaches it.
This one writes `from create_snowflake_db import initialize_database` off a
`sys.path` entry of its own directory, which imports a **second** module
object with its own globals — so the patch landed on a module nobody called,
and the run went straight back to waiting on an MCP server. The seeder
claims the bare name in `sys.modules` before importing `main`.

The DDL is upstream's, `AUTOINCREMENT`, `NUMBER(18,2)`, three-part names and
all, so seeding is itself a test of the dialect layer the agent writes
through. `2024Q4REIMBURSEMENT` is the table rule 6 of that shim exists for:
an unquoted identifier cannot start with a digit in either dialect.
