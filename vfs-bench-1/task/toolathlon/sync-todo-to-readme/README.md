# Sync TODO to README

`main` and `dev` of a LUFFY fork differ in two Python files. Extract every
`TODO` from the `.py` files on `dev`, apply only the additions, removals and
line-number moves that main-to-dev introduced, and commit the updated
`### 📝 Complete TODO List` section of `README.md` back to `dev`.

## What the port needed

The fake kept exactly one branch, and this task's entire premise is the
difference between two. mirage `84e1220d6` adds branches: a file map and a
commit list per branch, `branch_for` resolving a ref (branch name, `HEAD`,
or a commit sha) so a bad ref is a 404 rather than a silent read of the
default, ref-aware reads and writes, a per-branch root commit, and
`into=<branch>` seeding. `999832d2a` adds `GET /git/refs/{prefix}`, the
plural of a route that already existed in the singular — found by the
unrouted logger during the first mirage run.

`shared/fixtures/{main,dev}` is `Toolathlon-Archive/LUFFY` at both branches,
built by `shared/build_fixture.py` from the two verified commits in
`shared/sources.json`. 321 text files vendored verbatim per
branch, since the agent greps 233 `.py` files and a byte that moves is a
line number that moves; the 11 binaries — parquet shards, figures, a
notebook — are placeholders at the same paths, which is 9 MB of the 12 MB
tree.

The two branches differ in exactly `luffy/deepscaler/utils.py` and
`luffy/verl/verl/protocol.py`. Everything else is identical, which is what
makes "only apply the changes main-to-dev introduced" checkable rather than
a hint.

mirage mounts both branches, at `/repo/main` and `/repo/dev`, so the change
set is `diff -r` and the TODO survey is `grep -rn`. Not `/main` and `/dev`:
`/dev` collides with the device mount and the workspace refuses to build.

## Reproducing

```bash
uv run python server/mcp/setup_github.py        # needs Go; once per machine
uv run python agent/run_agent.py toolathlon/sync-todo-to-readme --tools vfs
uv run python agent/run_agent.py toolathlon/sync-todo-to-readme --tools mcp
```

Upstream's preprocess writes a `.github_token` into the workspace and the
brief mentions it. Neither arm here needs it — both authenticate through
their own configured surface, as the MCP arm does upstream — so the seeder
does not write one.
