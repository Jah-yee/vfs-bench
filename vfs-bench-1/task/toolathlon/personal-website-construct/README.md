# Personal website construct

Fork `academicpages/academicpages.github.io`, rename the fork to
`LJT-Homepage`, and fill its `_config.yml` and `_pages/about.md` in from the
person described in the memory server.

The first GitHub task, and the one that decided how the two arms reach a
repository at all.

## The mount is the read half; `gh` is the write half

mirage mounts the template at `/template`, so surveying a 315-file Jekyll
site is `find` and `ls` and reading three files is `cat`. What it could not
do was write: `GITHUB_IO` carries `readdir`/`read`/`stat` where `GDRIVE_IO`
carries the full set, so no commit was reachable, and forking and renaming
are account operations a filesystem has no shape for regardless.

mirage `7b1d7f7a7` adds `gh`, spelled as the real CLI spells it —
`gh repo view|fork|rename` and `gh api`. Committing a file is

```bash
gh api repos/OWNER/REPO/contents/PATH -X PUT \
  -f message="..." -f branch=master -f sha=BLOB_SHA \
  -f content="$(base64 -w0 /work/file)"
```

which is what real `gh` and real GitHub require of each other; there is no
file-writing verb to mimic. This is the same shape as
[apply-phd-email](../apply-phd-email/README.md), where `/mail` is the read
half and `himalaya` the write half, and the GWS tasks, where the mounts read
and the `gws` CLI writes.

**One tool the MCP arm has and mirage does not: `push_files`, a multi-file
commit.** mirage's `gh api` writes one file per call because real `gh` does.
That is a real difference in surface, not an artefact.

## Both arms had to stop being graded against a 404

The fake gained ten routes for this task, and two of them exist because of
a defect the task found rather than one predicted in advance.

Removing the template's demo pages takes `DELETE /contents`. The fake had no
such route, and every call came back 404. **To a real client a 404 is an
answer** — "no such file" — so an unimplemented endpoint is indistinguishable from a negative result, and what
comes out is a confident wrong conclusion rather than an error.

That is why the fake now logs every unrouted request by method and path.
`DELETE /contents` and `GET /commits/{ref}` are now implemented.

## The MCP server had to be built

Toolathlon ships a prebuilt `github-mcp-server` and says so itself in
`local_binary/github-mcp-version.txt`: *"this binary is built by go on linux,
so maybe can not be used on other platforms"*. It is an x86-64 ELF, so on
darwin/arm64 the arm cannot start.

`server/mcp/setup_github.py` builds upstream's pinned commit `ef07feb` from
source rather than substituting a current release — the tool surface is half
of what the MCP arm is measured on, and it has to be upstream's 91 tools.

It patches exactly one thing. `--gh-host` is the only place a base URL can
be set, and `newGHESHost` builds its URLs from `u.Hostname()`, which drops
the port. Upstream flags this directly above `parseAPIHost`: *"Note that
this does not handle ports yet, so development environments are out."* A
fake on `127.0.0.1:19801` is exactly that development environment, and
`u.Host` is the same string with the port kept. URL construction only; no
tool is added, removed or renamed.

Any host that is not github.com is read as Enterprise, which serves REST
under `/api/v3/` and raw content under `/raw/`. The fake serves every route
at both prefixes, so the MCP server reaches it as GHES while mirage's own
backend and the grader reach it as dotcom.

## Isolation is a restart, not a reset

`shared/seed_github.py` restarts the fake between arms. The other services
reset in place; this one cannot, because the state to clear is the whole
account rather than the two repositories the task names — the agent may
create any repository it likes.

This is the task where getting that wrong would be worst. Both arms fork the
same template into the same name, so an arm running second against a live
store would find `LJT-Homepage` already holding the other arm's answer and
could pass without writing anything. That is the
[oil-price](../oil-price/README.md) contamination, in the one task where it
would produce a clean pass out of nothing.

## The fixture

`shared/fixtures/academicpages` is the upstream template, vendored. Text
verbatim — the agent reads `_config.yml`, `_pages/about.md` and the layout
around them, and paraphrasing any of it would change the task. The 40 binary
assets are one-line placeholders at the same paths: nothing reads their
bytes, they are 3.6 MB of the 5.3 MB tree, and keeping the paths keeps every
directory listing the length the two arms are priced on.

`shared/build_fixture.py` rebuilds it from the verified commit in
`shared/sources.json`; it does not follow the moving default branch.

## The grader

`evaluation/check_remote.py` reads `_config.yml` and `_pages/about.md` from
`{user}/LJT-Homepage` at ref `master` and checks for substrings — the three
author fields, and in the about page a list that includes `NLP`, `Ph.D.`,
`Computer Science`, each internship's employer and each publication's
keyword. It is a substring grader, not a byte comparison, so unlike
[apply-phd-email](../apply-phd-email/README.md) neither arm is punished for
formatting.

`master`, not `main`: academicpages is one of the repositories whose default
branch never moved, and the grader names the ref literally, so the fixture
has to be served on it.

A golden solver filled the two files correctly,
so a failing arm and an ungradeable fixture cannot be confused.

## Reproducing

```bash
uv run python server/mcp/setup_github.py        # needs Go; once per machine
uv run python agent/run_agent.py toolathlon/personal-website-construct --tools vfs
uv run python agent/run_agent.py toolathlon/personal-website-construct --tools mcp
```

The batch restarts the fake before each arm and points the grader at it
through `redirect/eval_shim/github_host.py`, which rewrites
`api.github.com` onto the fake — `utils/app_specific/github/api.py`
hardcodes the host, so there is nowhere else to intervene.
