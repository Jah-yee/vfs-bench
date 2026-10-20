# Academic warning

Join `latest_quiz_scores.csv` against seven historical score tables in
BigQuery, write every student whose score fell more than 25% into
`bad_student.csv`, and write a CRITICAL Cloud Logging entry for each one
who fell more than 45%.

## Why this one can pass on both arms and live-transactions cannot

The two tasks look alike: read BigQuery, write a CRITICAL entry to a log
bucket found by prefix. They differ in one line of their evaluators, and
that line decides whether the MCP surface can answer at all.

This task matches on the entry's rendered payload:

```python
message = str(entry.payload)
if str(student_id) in message and str(student_name) in message:
```

`live-transactions` matches on its shape:

```python
if not isinstance(payload, dict): return False
```

`logging_write_log` -- the only tool on upstream's google-cloud server that
writes an entry -- declares `"message": {"type": "string"}` and stores a
`textPayload`. A string satisfies `str(payload)` and fails
`isinstance(payload, dict)`. So the same arm, with the same tools, passes
here and cannot pass there.

That is worth stating because it is the difference between "the model did
not manage it" and "the surface cannot express it". Only the second is a
result about tools, and only a pair of near-identical tasks makes it
visible.

## The three checks that had to be repaired first

None was this task's fault; all three were found porting these tasks
together and are described where they were found -- see `ab-testing`'s
README for the service-account key and the launch-time format, and
`live-transactions`' for `list_sinks` and the grading timezone.

This task's stake in them is that its evaluator does *not* fail quietly.
`get_project_id_and_credentials` returning nothing is followed by
`sys.exit(1)` with `❌ Failed to load project credentials`, where
`ab-testing` swallows the same failure and blames the agent. Having both in
the pool is the reason the missing key was diagnosable rather than merely
suspicious.
