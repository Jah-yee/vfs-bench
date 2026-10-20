# A/B testing

Read twenty scenarios of clickstream out of BigQuery, fill `record.csv` with
each version's conversion rate, and then act on the winner: create a Cloud
Storage bucket prefixed `promo-assets-for-b` if B wins, or write one Cloud
Logging entry if A does.

## The task's answer is a side effect, which is what the seed has to undo

`record.csv` is checked against `expected_ratio.csv`, but the first thing
the evaluator checks is whether a bucket matching `promo-assets-for-b`
exists. B does win, so the passing answer *is* the bucket -- and both arms
run one after the other against one emulator.

Recreating a bucket by name, which is what `shared/storage.json` meant
everywhere before this task, is exactly wrong here: an empty
`promo-assets-for-b` bucket is already the passing answer. What the seed has
to leave is nothing matching the prefix at all, which is what upstream's own
`preprocess/ggcloud_clean_bucket.py` does and what `seed_gcs.drop_prefixed`
now does. Without it the second arm inherits the first arm's bucket and is
graded as having created it.

`tests/parity.json` asserts the absence directly, so the property is checked
rather than assumed.

## Two harness defects this task was the first to reach

Neither is about A/B testing. Both were found because this is the first
ported task whose evaluator does something the others do not.

**The service-account key was never placed.** `evaluation/main.py` opens
`configs/gcp-service_account.keys.json` -- a bare relative path, resolved
against the checkout, that no environment variable can redirect. Every other
google-cloud evaluator so far builds a client and lets
`BIGQUERY_EMULATOR_HOST` or `STORAGE_EMULATOR_HOST` decide, so none of them
needed the file to exist. This one catches the credential failure, falls
back to `subprocess.run(['gcloud', ...])`, and reports that the bucket was
not created.

That is the shape to fear: a *correct* answer graded as a total failure,
with the evaluator's own message pointing at the agent.
`grade_task.place_gcp_key` copies the key the stack already generates to
where the evaluator opens it. `flagged-transactions`'s README predicted this
task would need it.

**The launch timestamp was the wrong format.** Upstream's runner builds it
as `"%Y-%m-%d %H:%M:%S %A"` (`utils/data_structures/task_config.py:312`) and
this evaluator parses it back with exactly that. The seed records
`"%Y-%m-%d %H:%M:%S"`, because the same field also clocks the BigQuery
emulator and is read by `bin/start.sh` and `server/api/app.py`.

The failure is quieter than the first one and worse for it.
`check_abtesting_logging_bucket_clean` wraps its whole body in `except
Exception: return True`, so an unparseable timestamp does not fail the
grade -- it skips the check and reports success. The task would be graded on
its bucket and its CSV while the assertion about log entries silently never
ran. `grade_task.upstream_launch_time` adds the weekday at the one point of
use rather than changing what the seed stores.

The three evaluators that parse launch_time this way are ab-testing,
academic-warning and live-transactions -- the three tasks ported together --
which is why nothing had reached it before.

## What "overall" means

The task defines the overall rate as "the arithmetic mean of the
per-scenario conversion rates", and the per-scenario rate itself as neither
of the two things it could be. Upstream's ground truth is
`sum(store_views) / sum(clicks)` per scenario -- the evaluator's own key
spells it, `"overall (total_store_views/total_clicks)"` -- not the mean of
the per-window ratios.
