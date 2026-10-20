# Apply PhD email

Find an email from `kaiming` in the inbox, gather the materials it asks for from
the workspace, and reply with them attached under an exact subject line.

## Issue #7 corrections

The workspace now starts with the extracted application files and no archive,
matching upstream preprocessing. Both MCP servers use locked dependencies.
VFS provides PyPDF2 3.0.1, the serializer used by `pdf-tools-mcp`, and documents
its page-copy operation. The live `merge_pdf_bytes` parity case produces
identical hashes through both arms; `tests/toolathlon_fidelity.py` also checks
the generated PDF against upstream's reference bytes without changing the grader.

## The task is decided by which library merges a PDF

The agent has to merge three award certificates into one PDF and attach it.
`evaluation/check_local_email.py` extracts the attachment and compares it to
the reference with `!=` — a **byte** comparison of a generated binary. So
passing does not mean producing the right PDF, it means producing upstream's
exact serialisation of it:

```
extracted (3020)  %PDF-1.4 … 1 0 obj << /Producer (pypdf) >> … /Info 1 0 R
reference (3021)  %PDF-1.4 … 1 0 obj << /Type /Pages /Count 3 /K … /Info 2 0 R
```

Same three certificates, same three pages, one byte apart in object ordering
and metadata. The only reliable way to land on the reference is to call the
same `merge_pdfs` the ground truth was generated with, from the `pdf-tools`
server.

This is the mirror image of
[music-analysis](../music-analysis/README.md),
where an unstated truncation rule punishes whichever arm reads the brief
literally. Here a byte-exact grader rewards whichever arm happens to reach
for the tool the reference came out of. Both are properties of the task, and
this one the shell surface cannot beat by being correct.

## Building the task

What follows is why the task is worth building and what it took to unblock it.

This is the first non-Google backend, and the one where the filesystem framing
is strongest: a mailbox *is* a tree, so mirage mounts it as one and reading it
is `ls` and `cat` rather than a search tool. mirage has the pieces already — an
`email` resource, a `gmail` resource, and a `himalaya` CLI whose verbs
(`envelope list`, `message send`) are the write half.

Servers: `emails`, `filesystem`, `terminal`, `memory`, `pdf-tools` — all local.
Only `emails` needs a backend stood up; the rest operate on the workspace.
Chosen over the alternatives because it is email-centric rather than email plus
something else: `course-assistant` drags in `excel`, `email-paper-homepage`
needs a live GitHub with real repos, and `set-conf-cr-ddl` /
`student-interview` needed a Google Calendar mock that mirage had no resource
for when this was chosen. mirage `5a95be6ac` added one — `gws calendar`, and a
`gcal` mount — so those two are portable now.

The mail backend was the first blocker and is solved. `emails` speaks IMAP/SMTP
to `localhost:1143` / `1587` (`shared/emails_config.json`), which upstream
serves with poste.io in Docker. `bin/start.sh up` runs **GreenMail** on the
same ports instead, and `-Dgreenmail.auth.disabled` makes any login succeed and
creates the mailbox on first use, so a task brings its own cast of addresses
with no per-account setup. `server/seed/seed_mail.py` loads either upstream fixture
shape (`emails_backup.json` or `emails.jsonl`) over IMAP APPEND. Both already
carry `course-assistant` and `git-bug-hunt`.

The second blocker was attachments: the reply has to carry them and mirage's
`himalaya` had no `--attach`, so the write half was unreachable. That is fixed
upstream and verified — a real `multipart/mixed` with filename and payload
intact, by mirage #723.

That caveat — whether the task needs attachments *read* as PDFs or only
forwarded as bytes — is now answered: it needs them **written**. The agent
merges three certificates into one PDF, which is why `pdf-tools` is in the
server list, and it is the whole of the difficulty above. The mirage arm gets
`pypdf` from `/opt/wheels` under the pyodide runtime and merges correctly; it
just does not merge *byte-identically*.

## Reproducing

```bash
bin/start.sh up                       # GreenMail on 1143/1587
uv run python agent/run_agent.py toolathlon/apply-phd-email --tools vfs
uv run python agent/run_agent.py toolathlon/apply-phd-email --tools mcp
```

The batch resets the mailbox between arms and then reloads it, which this
task needs. `shared/receiver_config.json` is the mailbox the reply is sent
*to*; the fixture is addressed to `mary.castillo@mcp.com` and both arms mount
`shared/emails_config.json`. The branch loads the backup into the latter
and creates the former empty so the send has somewhere to land.
