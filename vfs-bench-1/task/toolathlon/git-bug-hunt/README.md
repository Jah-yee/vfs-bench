# Git bug hunt

Find the earliest commit in the `LUFFY` repository that introduced the
variable `remove_caching_layer`, then email its author the commit hash and
message under the subject `[URGENT] Performance Issue Investigation
Regarding Your Commit`, formatted per `template.txt`.

**Both arms have a shell.** Toolathlon gives this task the `terminal` server.
Toolathlon's `git_log` exposes only `repo_path`, `max_count`,
`start_timestamp` and `end_timestamp`, so the pickaxe the task needs cannot
be spelled through it. Refs resolve as real git resolves them — `main` and
`origin/main` genuinely differ here.

The fixture is 60 commits, 8 authors, 511 files of a real RL codebase; four
single-commit authors are planted among 54 real ones and exactly one commit
contains the string. It is read from the Toolathlon submodule rather than
copied — the tarball is 24 MB.

Caveat: `bin/start.sh up` runs **GreenMail** with `-Dgreenmail.auth.disabled`
on Toolathlon's ports, not upstream's poste.io. Neither arm files a copy in
`Sent` — GreenMail has no such folder and mirage's himalaya has no IMAP
`APPEND` — so the two behave alike. `verify_mock.py` is a port of upstream's
`check_email_content.py`: same subject filter, same three regexes, same lenient
commit-message comparison, same four phrases proving the template was used.

```bash
bin/start.sh up start
AGENT_WORKSPACE=/tmp/gbh uv run python task/toolathlon/git-bug-hunt/shared/seed_mock.py
AGENT_WORKSPACE=/tmp/gbh uv run python agent/run_agent.py \
    --task-dir task/toolathlon/git-bug-hunt --tools vfs
uv run python task/toolathlon/git-bug-hunt/shared/verify_mock.py
```
