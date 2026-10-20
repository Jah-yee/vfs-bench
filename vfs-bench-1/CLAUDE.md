# Working on this Repo

Two tool surfaces are compared over identical fixtures, so a change may move
**where bytes come from** but never **what the model is sent**.

## Rules

**Never invent anything about a task's settings or this repo's structure.**
If upstream does not have it, it does not go in: not a flag, not a config
key, not a directory, not a mode -- and where upstream does have it, it is
copied rather than improved.

> `run_agent.py` grew a `--no-seed` and a `--no-grade` that upstream's own
> runner has no equivalent of. Each was a minute saved for whoever added it
> and a whole class of run whose grade means nothing: one measured against
> whatever the previous run left behind, one not measured at all. They also
> cost a workspace-resolution path that existed for no other caller.

**Never spawn a sibling module; import it and call a function.** A
subprocess to code in this project on this project's dependencies buys
nothing and costs the traceback, the callability from tests, and an
interpreter start -- earn one only where the callee is genuinely foreign,
like a task's own seeder.

> `set-conf-cr-ddl` spelled `task/toolathlon/script/seed_mail.py` in a
> subprocess argv. The file moved to `server/seed/`, nothing resolves a
> string, and the task could not be seeded at all until a draw was run.

## Data Lineage

Every committed fixture traces back to its source through a `dvc.yaml` stage,
so the data both arms read stays as close to upstream's as it can be. Add a
stage whenever you add a fixture with a source it could drift from, and ask
`uv run dvc status` what has drifted.

> Bump `submodule/Toolathlon` and `dvc status` names every task whose upstream
> `task.md` moved. Nothing else in the repo would notice.

## MCP Lineage

Run upstream's own server, at upstream's version, with upstream's args, and
declare every divergence in `server/mcp/mcp_servers.py` -- a fork changes tool
names, descriptions or schemas, which is the one thing being measured. Pin the
tree and not just the server (`package-lock.json` for the sixteen vendored
npm trees, `uv.lock` for the eleven Python ones, a commit hash for the Go
one), and read upstream's own config through `mcp_servers.upstream_config()`,
which reads `git show HEAD:` rather than a working tree we patch in place.

> `@modelcontextprotocol/sdk` is transitive and serialises the schemas, so an
> unpinned SDK moves measured bytes without touching a line of this repo.

## Repo Layout

Leave it where it is: paths are spelled in shell, compose files, yaml comments
and `.env.example`, none of which anything checks, so a move fails later and
somewhere else. If you must move something, grep the old path across every
file type, not just Python.

> Moving the checkouts under `submodule/` left `docker/Dockerfile` unbuildable,
> fifteen workspace yamls naming a deleted file, and `.env.example` still
> setting `TOOLATHLON_ROOT=./Toolathlon`. That last one is the shape to fear:
> `run_agent.py` loads the file into the environment and the seam reads the
> variable *before* its own default, so the stale value overrode the correct
> one rather than merely being out of date.

## Submodules

Upstream's four checkouts are gitlinks under `submodule/` -- Toolathlon,
toolathlon_gym, mirage and mcp-atlas -- so clone with
`--recurse-submodules` and never vendor a copy in their place. The lint CI is
the one exception, and only for itself: `.github/workflows/lint.yml` checks
out without them, because every hook it runs is `repo:`-based and installs
its own environment, and it skips the one local hook that needs this
project's dependencies, `fixture-lineage`. Bumping one is a deliberate act
rather than a `git pull`, because it can move the task text, the tool schemas
and the fixtures at once; re-run `uv run dvc status` and `tests/parity.py`
after.

> mirage is installed editable and lives under `submodule/` and not the repo
> root, where a `mirage/` directory would shadow the package: `import mirage`
> would resolve the repo root as a namespace package.
