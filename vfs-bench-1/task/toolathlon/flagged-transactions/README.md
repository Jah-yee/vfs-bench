# Flagged transactions

Both surfaces expose the same five-row preview of query results.

Pull 2025 transactions for twenty high-net-worth clients out of BigQuery,
flag the ones above `mean + 3*std` for their own client, and write them into
`anomaly_audit_report.xlsx` sorted by transaction id.

What the two surfaces weigh, counted locally by booting every server the
task declares:

| arm | tools | tool-schema bytes |
|---|---:|---:|
| mirage VFS | **1** | one shell over the mounts |
| Toolathlon MCP | **80** | **44,867** |

| server | tools | bytes |
|---|---:|---:|
| google-cloud | 39 | 21,293 |
| excel | 25 | 14,359 |
| filesystem | 14 | 8,165 |
| terminal | 2 | 1,050 |

Bytes are not tokens — this is the shape of the
thing being measured. Tool definitions are re-sent on every request and are
not cached, so 39 of those 80 tools exist to describe a Google Cloud the
task reaches through one dataset.

## The emulator mislabelled a user SQL error

A query with a typo should get a 400 and a one-turn recovery. Through the
emulator it did not, and the cause was ours:

| layer | what happened |
|---|---|
| mechanism | `client.query()` retried the job insert — 0.3s, 1.4s, 5s, 30s — to a ~10-minute deadline |
| why | `jobInternalError` is in `job_retry_reasons` (`bigquery/retry.py:138-142`) |
| trigger | the emulator answered HTTP 200, job `DONE`, `errorResult.reason = "jobInternalError"` |
| correct | real BigQuery returns `invalidQuery`, which maps to 400 (`bigquery/job/base.py:47`) and raises at once |

`goccy/bigquery-emulator` labels a deterministic *user* SQL error as a
transient *internal* one, and one word in a JSON field is the whole
difference between "fix your query" and a ten-minute retry storm.

**It hits one arm only.** The `bq` CLI posts to `/queries`, the synchronous path, which
returns a clean 400 carrying `failed to analyze: Unrecognized name: RO [at
1:54]`. Upstream's server uses `client.query()` → `/jobs`, the asynchronous
job API, where the mislabelled reason lives. Same emulator, same bad SQL:
invisible to mirage, fatal to MCP.

Reproduced with no MCP in the picture at all — calling the server's own
`run_query()` in-process hangs past 150s on bad SQL and returns in 0.43s on
good.

`server/bq/proxy.py` is the fix: it sits in front of the emulator and
relabels that one field, so the fake fails the way the service does rather
than either arm being special-cased. Requests are untouched, no other
response is altered, and `/queries` — the path the `bq` CLI uses — passes
through unchanged, so the correction cannot advantage the arm that was never
affected.

Through the proxy the same bad query raises `BadRequest` in **0.10s**
instead of hanging past 150s.

## The lesson, which is not about BigQuery

Both defects this port has turned up were ours:

* `bq` did not declare `--format`, so mirage's parser folded
  `--format=prettyjson` into the statement and the engine rejected SQL the
  agent never wrote. This is the `ntn` lesson again, and it was written into
  the very CLI that lesson is about.
* the emulator's error reason, above.

The `--format` fix above was first
applied to `bq query`, the verb that had failed, and not to `ls` or `show` —
the instance was fixed and the class was not. game-statistics walked into the
other two verbs, which is what finally made the flag global. **A defect found on
one surface is a question about the whole surface**, and answering only where
it hurt leaves the rest of it armed.

Neither would have been visible from a passing run — the
happy path was green in both cases. **A fake's error semantics are as
load-bearing as its results**, and the fifteen-case probe that cleared this
emulator tested almost only success. The storage and logging stages get their
failure modes tested before anything is measured.

## The first google-cloud task

This is the first of Toolathlon's eight `google-cloud` tasks to be ported,
and it is first because it is the cheapest: its evaluator imports no Google
library at all. It reads the agent's xlsx and diffs it against a committed
groundtruth, so the fake has to satisfy the *agent* and nobody else. The
other seven all read something back out of GCP.

The eight tasks split by service, and the split is lopsided:

| service | tasks | what the agent does |
|---|---:|---|
| BigQuery | 8 | every task; 5 read-only, 3 also write |
| Cloud Storage | 3 | write-only — one blob, or one bucket |
| Cloud Logging | 3 | write-only — no task ever reads a log |

So BigQuery is the whole of the surface here: this task's own
`token_key_session.py` sets `google_cloud_allowed_buckets` and
`google_cloud_allowed_log_buckets` to `"null"`, and upstream's server is
launched with the storage and logging tools switched off.

## No shim, an emulator

The `snowflake` tasks needed `redirect/snowflake` — a dialect layer rewriting
Snowflake SQL onto Postgres, and a shadow package so three different readers
land on it. BigQuery needs none of that, because
[`goccy/bigquery-emulator`](https://github.com/goccy/bigquery-emulator)
speaks the real REST API. Every reader points at one process:

| reader | how it is pointed |
|---|---|
| Toolathlon's evaluators | `BIGQUERY_EMULATOR_HOST` |
| the `google-cloud` MCP server | `BIGQUERY_EMULATOR_HOST` |
| the mirage arm's `google-cloud` CLI | `BIGQUERY_EMULATOR_HOST`, the same server |

`BIGQUERY_EMULATOR_HOST` is not ours: `google-cloud-bigquery` honours it in
`_helpers.py:_get_bigquery_host`. There is no dialect rewrite for the two
arms to disagree about, and a GoogleSQL gap is a property of the emulator,
paid by both.

    uv run python server/mcp/setup_google_cloud.py   # once
    uv run python server/fakes/gcp.py flagged-transactions

seeds it from upstream's own `files/all_transactions.csv` — 10,000 rows via
`server/seed/seed_bigquery.py`, which reads
`task/toolathlon/flagged-transactions/shared/bigquery.json` to learn that the CSV is
`all_transactions.recordings`. Nothing is captured and nothing is invented;
the seed file is generated rather than committed, so it stays in step when
the submodule pin moves.

## The fixture reproduces upstream's ground truth exactly

The committed `groundtruth_workspace/anomaly_audit_report.xlsx` holds 59
rows. Running the per-client threshold as one GoogleSQL statement against
the emulator returns the same 59, in the same order, with identical
`client_id`, `transaction_id` and `txn_time` — and upstream's own evaluator
then prints `Pass all tests!` and exits 0.

Two details had to be right for that:

**`txn_time` is a STRING, not a TIMESTAMP.** The column reads
`2025-04-15 22:36:01.357628 UTC`, and BigQuery's `autodetect=True` left it a
string — upstream's preprocess proves it, reading the column back with
`PARSE_DATETIME('%Y-%m-%d %H:%M:%S.%f UTC', txn_time)`, which is a type error
against a TIMESTAMP. `shared/bigquery.json` pins the type so inference
cannot drift onto a temporal one and silently break the year filter.

**The threshold is per client, not global.** `docs/task.md` says "for each
client" and the committed xlsx agrees: 59 rows spread 2–4 across all twenty
clients. The `anomaly_detection.py` sitting in `groundtruth_workspace`
computes a *single* global mean and standard deviation, which yields 12 rows
— it does not generate the file it sits next to. The xlsx is the graded
artefact, so the xlsx is what the port is checked against.

## The MCP arm needs a key that mints its own tokens

`BIGQUERY_EMULATOR_HOST` redirects the endpoint and nothing else. Unlike
`STORAGE_EMULATOR_HOST`, which swaps in `AnonymousCredentials` when none was
passed, the BigQuery override leaves an explicit credential in place
(`client.py:267-272`) — and both the MCP server (`src/big_query.py:31`) and
Toolathlon's evaluators pass one, built from
`configs/gcp-service_account.keys.json`. So the key has to sign a real JWT
and exchange it somewhere.

`server/bq/token_stub.py` is that somewhere: it generates an RSA
service-account key whose `token_uri` points back at itself, then answers
the exchange. `uv run python server/fakes/gcp.py` runs it alongside the emulator. The key path
is already in upstream's `.gitignore`, so the generated file does not dirty
the submodule.

A monkeypatch would have been worse: it would have to reach the MCP server,
the evaluator, and the two evaluators that `open(CREDENTIALS_PATH)`
unconditionally at import — and it would still miss `ab-testing`, which
swallows a credential failure at `main.py:121` and falls back to
`subprocess.run(['gcloud', 'storage', 'buckets', 'list', ...])` that no
environment variable can redirect.

The server itself is vendored rather than `uvx`-resolved, for two reasons
`server/mcp/setup_google_cloud.py` spells out: `uvx` floats, and the tool
schemas are the denominator of every saving number; and PyPI 1.0.0 gates
resources by exact set membership, which denies `ab-testing`'s
`promo-assets-for-b*` for every name but that literal. Both expose the same
39 tools.

## Backquotes need single quotes

`bq query "SELECT * FROM \`ds.tbl\`"` does not work, and the failure is the
shell's, not the engine's: a backquote inside double quotes is command
substitution, so the statement arrives mangled and the emulator answers
`failed to parse statements`. `SKILL.md` shows the two spellings that do
work — single-quoting the statement, or dropping the backquotes, which
GoogleSQL also accepts.

This is the kind of detail the `ntn` port showed is worth getting right: a
CLI that *nearly* matches a grammar the model knows costs several times one
that matches it.
