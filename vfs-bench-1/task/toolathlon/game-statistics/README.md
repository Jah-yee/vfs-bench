# Game statistics

End-of-day settlement: build `leaderboard_YYYYMMDD` from the day's top 100
players in `daily_scores_stream`, and append every player's daily totals to
`player_historical_stats`.

| arm | tools |
|---|---:|
| mirage VFS | **1** |
| Toolathlon MCP | **47** — google-cloud 39, local 6, terminal 2 |

## The fixture is generated, not committed

Every other ported task reads its fixture out of upstream's `files/`. This
one has no `files/`. Its preprocess *generates* the data — 200 players,
1,314 games, ten prior days of history — and the answer table is named after
the day the run happens. Freezing that output would produce a fixture that
is wrong the day after it is written, and a `leaderboard_20260813` that
nobody would be asked to build again.

So the port runs upstream's generator instead, at run time. `uv run python server/fakes/gcp.py`
starts the emulator empty and then runs their preprocess against it, which
`shared/bigquery.json` asks for by naming the module rather than a CSV:

    {"project": "mcp-bench0606",
     "preprocess": "tasks.finalpool.game-statistics.preprocess.main"}

Two things had to be fixed for that to work, both in `redirect/bigquery`:

**The emulator has no NDJSON load path.** `load_table_from_json` posts to
`/upload/bigquery/v2/.../jobs?uploadType=multipart` and gets `500 failed to
add job`. CSV loads and streaming inserts both work, and CSV cannot express
the nested `scores` RECORD, so the shim reroutes that one method through
`insert_rows_json` — same rows, same table, same write disposition.

**The generator is only half-seeded.** Upstream sets `random.seed(42)` at
module scope, so reproducibility is their intent, not an idea imposed here.
But every draw goes through `random` except one: `generate_player_skill_level`
calls `np.random.normal(50, 15)`, and numpy keeps its own generator that
nothing seeds. Skill sets every score, so the fixture came out different each
run:

    unseeded numpy: 34.948366   seeded random: 31
    unseeded numpy: 42.649466   seeded random: 31

That matters because the reset between arms *is* a preprocess re-run. Seeding
numpy to the same 42 finishes the seeding upstream started; it chooses which
draw from their generator and changes nothing about the shape of the data or
the difficulty of the task. Verified: two full preprocess runs, and a third
through a container restart on a different clock, all produce byte-identical
tables.

    stream  4161b51318c452090182cb0a192be829637ead2e4459d170fff72f3cd0c70245
    history bd8f869ff4a2070e0d94ef104c74abd806e28973f46565af7434f4f6a4aa6a51

Neither arm is told the date. Both have to find it in `daily_scores_stream`.

## The two corrections

**`--format` was declared only on `query`.** Real `bq` takes it globally.
This is the same defect flagged-transactions found, still sitting on the two
verbs that had not yet bitten anyone. Now every
verb takes it, and an undeclared flag is refused by name everywhere instead
of being folded into an operand.

**The struct was passed through raw.** `scores` is a RECORD, and BigQuery's REST
API sends one as an envelope — `{"f":[{"v":"622"},{"v":"549"}]}` — which this
CLI was passing straight through. `TIMESTAMP` had the same problem, arriving as the epoch
float `"1786582260.000000"` where real `bq` prints `2026-08-13 10:11:00 UTC`
— on a task whose whole question is *which rows are today's*. The CLI now
unwraps both. The Python client the MCP arm uses decodes both before the
agent is shown anything.

## What is still slightly wrong, and was not fixed

Job-based queries leave a temp dataset behind in the emulator, so after a run
`bq ls` lists a dozen UUIDs alongside `game_analytics`. Real BigQuery hides
its anonymous datasets.

It is asymmetric: every caller of `client.query()` creates one — the MCP
server and upstream's evaluators both — while the `bq` CLI's synchronous
`/queries` path creates none. Checked directly against a fresh emulator, with
`SELECT`, `CREATE TABLE`, `INSERT` and `CREATE TABLE AS SELECT`: the dataset
list was unchanged after all four.

The evaluator's two are created after grading has already read what it
needs.

Recorded rather than fixed, because the fix
would mean filtering responses in the proxy on suspicion. If a later run
lists datasets late and trips on it, that is where the fix goes.

## A note upstream's preprocess leaves behind

It writes `groundtruth_workspace/task_date.txt` into the submodule so its
evaluator can recover the date. That is upstream's own behaviour, it is
untracked, and this repo's parent `git status` ignores it. The port passes
`--launch_time` to both halves explicitly instead — `uv run python server/fakes/gcp.py` prints
`BQ_LAUNCH_TIME` for exactly that — so the evaluator never has to fall back
to the file.
