# Price comparison

Read our ten product prices out of a CSV and the competitor's out of a PDF,
match them up, and write product name, both prices and the difference into
BigQuery as `bigquery_pricing_analysis.analysis`.

## The first ported task whose agent writes the warehouse

flagged-transactions reads BigQuery; this one creates a table in it.
Upstream's preprocess deletes `bigquery_pricing_analysis` and recreates it
*empty*, so the fixture is a dataset with nothing in it and making the table
is the task. `server/seed/seed_bigquery.py` grew a `datasets` key for that — a
manifest can now name a dataset without naming a CSV, and

    {"project": "mcp-bench0606", "datasets": ["bigquery_pricing_analysis"]}

is the whole of `shared/bigquery.json`. An empty dataset is reported rather
than skipped when seeding, so it stays distinguishable from a manifest whose
CSV silently read as zero rows.

Because the agent writes, the fixture has to be put *back* between arms. The
emulator is restarted rather than the table dropped: an arm is free to create
whatever it likes, and only a restart returns the dataset to what upstream's
preprocess leaves. This is the same reason `agent/run_agent.py` wipes the
agent workspace before it seeds.

## The write paths were probed before anything was measured

flagged-transactions ended with a note that a fake's error semantics are as
load-bearing as its results, and that the probe which cleared the emulator
had tested almost only success. DDL, DML and the load-job path were all
unexercised then, so they were probed here first — through the MCP server's
own code, in-process, against the running emulator:

| path | result |
|---|---|
| `CREATE TABLE` with spaced column names | 0.15s, ok |
| `INSERT`, with and without a column list | 0.14s, ok |
| `SELECT` backquoted and ordered | 0.29s, rows |
| `bigquery_load_csv_data` (load job) | 0.03s, ok |
| unknown column / syntax error / unknown table / wrong arity | **0.02s each, `invalidQuery`** |
| dataset outside the allowlist | refused by the server, not the engine |

The four error cases are the ones that matter: 0.02s and `invalidQuery`
means `server/bq/proxy.py` corrects DDL and DML failures too, not only the
`SELECT` case that motivated it. Without the proxy each of those would have
been a ten-minute retry storm, and this task gives an agent four more ways to
write bad SQL than the last one did.

Only one gap turned up, and it is cosmetic: `bigquery_get_dataset_info`
answers `Location: Unknown, Created: Unknown` because the emulator does not
keep dataset metadata. Nothing reads it — not the task, not the evaluator.

## The fixture reproduces upstream's ground truth exactly

Before either arm ran, the ten rows from
`groundtruth_workspace/competitive_pricing_analysis_ground_truth.csv` were
inserted through the same `bq` CLI the agent uses, and upstream's own
evaluator scored them: 10 found, 10 perfect matches, 100.0% accuracy,
`EVALUATION PASSED`. So a failing arm here is the agent's failure and not the
fake's.

## Spaces in column names

`requirement.md` names the columns `Product Name`, `Our Price`, `Competitor
Price` and `Price Difference`, and the evaluator reads them back with
`` ORDER BY `Product Name` ``. None of those is a bare identifier, so every
one has to be backquoted in the schema and in every query — and a backquote
inside double quotes is command substitution to the shell. `SKILL.md`
carries both halves: single-quote the statement, and backquote the columns.
