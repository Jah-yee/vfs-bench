# Email paper homepage

Read the mailbox for acceptance notices, update the venue of every paper on
the homepage still marked "preprint" or "under review", and set `codeurl`
for each paper whose GitHub repository says the code is released.

## The stale mailbox was a conversion defect

The committed upstream `importable_emails.json` says COML 2026, but upstream
regenerates that file during preprocessing. Its pinned formatter and
`groundtruth_workspace/today.txt` produce COML 2025, matching the evaluator.
This repository incorrectly imported the stale output. That was a conversion
defect here, not an upstream grader defect.

`shared/derive_mail.py` now invokes the original loader and formatter using
upstream's JSONL, placeholders, receiver and checked-in date. DVC tracks all
those inputs. Seeding verifies the resulting 17 messages before importing
them. Export-time bookkeeping is omitted; every imported message field is
preserved.

## What the port needed

`shared/fixtures/` is five repositories vendored from `Toolathlon-Archive` —
the homepage plus the four paper repositories — and each is seeded under
**both** owners. That is not redundant: the grader reads the initial commit
sha from `Toolathlon-Archive/<name>` and the latest from `<login>/<name>`,
then asks what changed between them. It only works if a mirror preserves
shas, which real git does, so mirage `56f992f58` derives a branch's root sha
from its content rather than from the repository's name. Two branches still
differ exactly when their trees differ.

`My-Homepage` is on `master` and the four paper repositories on `main`; the
grader spells that difference out in its own `get_branch`, so the fixture
keeps it.

Two more routes, both found by the unrouted logger:
`GET /users/{login}/repos`, which is how "is there a repository for this on
my GitHub" gets answered and whose 404 read as "the account has none", and
`GET /repos/{owner}/{repo}/contents` with no trailing slash, which GitHub
serves alongside the slashed spelling.

The mailbox is the regenerated output of upstream's pinned preprocessing,
stored in `shared/importable_emails.json` and loaded through IMAP into
GreenMail for each arm.

## Reproducing

```bash
bin/start.sh up
uv run python server/mcp/setup_github.py        # needs Go; once per machine
uv run python agent/run_agent.py toolathlon/email-paper-homepage --tools vfs
uv run python agent/run_agent.py toolathlon/email-paper-homepage --tools mcp
```
