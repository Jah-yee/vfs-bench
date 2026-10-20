# Oil price

Both arms read `CL=F` and `BZ=F` live from Yahoo, as upstream does
([Live Yahoo](#live-yahoo--2026-09-25), #80). The grader refreshes its Yahoo
configuration on every run and, before the evaluator runs, checks that the
evaluator's server returns a close for each month it grades.
The fixture discussion below predates that change: the
generated price histories, and the Round 3 capture of 1,008 real bars that
replaced them, are both gone.

Pull twelve months of WTI and Brent futures closes from Yahoo Finance, work
out the Brent-WTI spread and its month-on-month change, standardise it into a
six-month z-score, backtest a spread strategy off that z-score, and write both
the monthly series and the backtest into two Notion tables.

## The arms were not starting from the same fixture

The task appends rows to two Notion tables that ship empty, so it has to be
reseeded before *every* run — its own
[`shared/seed_notion.py`](shared/seed_notion.py) says so in its docstring,
and the manual recipe below has always done it.
The batch runner of the day did not. It reseeded a task's `seed_db.py` and
`seed_mock.py` between arms and had no branch for `seed_notion.py`.
`task.json` now declares all three, so a runner cannot skip one.

The other notion tasks were unaffected — they reset inside their
`seed_db.py`, which the batch does call. Only the one whose seeder is spelled
differently was missed, which is why it went unnoticed for so long.

## Where the task comes from

`shared/author_fixture.py` reads the `Oil Price` subpage of the same public
template every notion task is duplicated from, through notion.site's record
API, and rewrites it into the shape mirage's fake seeds from — see
[`task/toolathlon/shared/notion_template.py`](../shared/notion_template.py). Both
tables come across with their real column ids and their real select options,
which matters: `Regime` already offers `High`/`Neutral`/`Low` and `Signal`
already offers `Short Spread`/`Flat`/`Long Spread`, so the vocabulary the
grader compares against is the template's rather than something an agent has
to guess. Each table also ships the one empty row Notion creates with a table,
and that row is load-bearing — it is the only place a client can read the
column list from without a schema call.

Before 2026-09-25 the prices were not upstream's. Toolathlon reads `CL=F` and
`BZ=F` from the live API; this repo read `shared/market/`, where both
contracts were authored by `script/author_prices.py`, both since removed.
Brent is **derived from**
WTI there, displaced by a mean-reverting spread, because two independent
random walks drift apart by tens of dollars over twenty months and the spread
— the entire subject of this task — would change sign. The evaluator prices
its own expected answer from the same rows through the same server, so the
task is exactly as hard as upstream intended; only the numbers differ.

Two consequences of the substitution, both symmetric across the arms:

- **`--interval` is ignored.** `pg_adapter.history()` takes the argument and
  never uses it, so `interval=1mo` returns daily bars on every surface,
  including the evaluator's. Everyone has to reduce to month-end closes
  themselves, and everyone does it the same way — the last session in the
  month.
- **The graded window slides.** `_get_expected_months()` is computed from
  `utcnow()` at grading time, and the task's `"anchor": "today"` fixture lands
  the newest bar on today, so the twelve graded months are always the tail of
  the series.
  The spread's parameters were tuned over five months of that drift rather
  than against one date.

## Two graders, two problems

**Sharpe is pinned to a convention the task never states.** `detail.md`
specifies the z-score's deviation to the ddof, the cost to the basis point and
the month format to the character — and then asks for a "Sharpe ratio" with no
definition at all. The evaluator computes it over a **twelve**-entry monthly
return series, zero-padded in every month where no position closed, with a
sample deviation.

The evaluator explicitly accepts *two* annualisation conventions for Annualized Return % and reasons
about it at length in a comment; it accepts one for Sharpe, and the task
statement names neither.

**The MCP arm could not see the select options.** Real Notion on
`Notion-Version: 2022-06-28` — which is the version the notion MCP server
sends — answers `API-retrieve-a-database` with the full column schema, select
options included. mirage's fake returns the 2025-09-03 shape regardless of the
requested version: `databaseJson` omits `properties` deliberately, because in
2025-09-03 the schema lives on the data source. `0f80101e3` fixed it — the fake now
versions its database object, so a request on `2022-06-28` gets the schema
with its select options.

The mirage arm reads the same schema off the mount, as a file
(`data_source.json`).

A golden solver graded `success` — twelve summary rows, one metric row, four trade rows, every cell matching — so the
environment is solvable and the fixture and evaluator agree.

## Running it

```bash
bin/start.sh up &                                   # fake Notion
uv run python server/seed/seed_task.py oil-price # the two Notion tables
uv run python server/mcp/setup_notion.py                   # once, for the MCP arm
uv run python task/toolathlon/oil-price/shared/seed_notion.py     # before every run

uv run python agent/run_agent.py --task-dir task/toolathlon/oil-price --tools vfs
uv run python agent/run_agent.py --task-dir task/toolathlon/oil-price --tools mcp
```

Re-seeding before every run is not optional: the tables ship empty and the
agent appends to them, so a leftover `Trade` row from a draw that found four
trades is an outright wrong answer for a draw that finds three. `server/seed/seed_task.py` now runs
`seed_notion.py` before every arm alongside the other two seeders, so

```bash
uv run python agent/run_agent.py toolathlon/oil-price --tools vfs
uv run python agent/run_agent.py toolathlon/oil-price --tools mcp
```

is equivalent to the recipe above.

The evaluator needs the task's Notion shim on its `PYTHONPATH`, which
rewrites `api.notion.com` onto the fake, and a `yahoo-finance` server that
answers live. `task/toolathlon/script/grade_task.py` sets up both, checks
that server first ([Live Yahoo](#live-yahoo--2026-09-25)), and then runs:

```bash
(cd submodule/Toolathlon && env \
   PYTHONPATH=../../task/toolathlon/oil-price/toolathlon/eval_shim \
   NOTION_URL=http://127.0.0.1:5091 NOTION_TOKEN=oil-price \
   uv run -m tasks.finalpool.oil-price.evaluation.main \
   --agent_workspace <ws> --res_log_file /tmp/stub.json)
```

so grade with it rather than by hand:

```bash
uv run python task/toolathlon/script/grade_task.py oil-price --agent-workspace <ws>
```

It also starts a `yahoo-finance` MCP server of its own, from Toolathlon's
`configs/mcp_servers/yahoo-finance.yaml`. Upstream points that at
`./local_servers`, which does not exist in this checkout, and the evaluator
swallows the failure — **with no prices it compares nothing and prints
success**. `setup/toolathlon/setup_toolathlon.py` rewrites the config to run the gym's copy
against the fixture; without that step this task grades every answer as correct.

## Live Yahoo — 2026-09-25

`CL=F` and `BZ=F` are now read live on both arms, as upstream reads them,
and the capture is gone. The evaluator's own `yahoo-finance`
server still comes from the rewritten config, which now runs the gym's copy
live. Before grading, `grade_task.py` checks that it returns a close for
each of the twelve months the evaluator grades, pricing a month the monthly
series skips by date on its last day as the evaluator does, so a transport
failure or an unpriced month cannot pass as the evaluator's silent
success. The grader's `PYTHONPATH`
under [Running it](#running-it) is now the Notion shim alone, with no
`PG_*` variables.
