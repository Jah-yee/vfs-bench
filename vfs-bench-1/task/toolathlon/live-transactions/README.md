# Live transactions

Find everything about transaction `T8492XJ3` across ten tables in BigQuery,
consolidate it into one JSON object with the user's other transactions under
`related_transactions`, upload it to the archive bucket, and write a
CRITICAL alert to the `Trading_Logging` bucket.

## The MCP arm cannot pass this task

The final step asks for a *structured* payload:

```
{'alert_type': 'Fraud', 'transaction_id': 'T8492XJ3', 'status': 'Pending_Investigation'}
```

and the evaluator checks it with `validate_log_payload_structure`, whose
first line is `if not isinstance(payload, dict): return False`.

The only tool on upstream's google-cloud server that writes a log entry is
`logging_write_log`, and its schema declares

```json
"message": {"title": "Message", "type": "string"}
```

A string reaches `CloudLoggingManager.write_log`, which branches on
`isinstance(message, str)` and calls `logger.log_text` -- so what is stored
is a `textPayload`. Never a dict. None of the other thirty-eight tools
writes an entry at all.

`needed_mcp_servers` is `filesystem` and `google-cloud`, with no `terminal`,
so there is no shell to route around it with. The task is unpassable on that
surface, and would be against real Google Cloud too. This is not a defect in
the port; it is the port measuring something.

## Two harness defects it found on the way

See `ab-testing`'s README for the three that task found.

**`list_sinks` reached the real Google Cloud.**
`redirect/cloud_logging` replaced five `ConfigServiceV2Client` methods and
said so: *"Sinks, exclusions and views are not replaced -- no ported task
touches one."* True until this task. `logging_list_logs` lists the buckets
and then lists the sinks to show what routes where, so the one unpatched
method turned the whole tool into `401 Request had invalid authentication
credentials`.

The task says "the log bucket whose name **prefixed by**
`Trading_Logging`", so listing is how the full name
`Trading_Logging-cc616b9e7c85` is found.

**Grading ran in the wrong timezone.** Even with the entry written and
visibly in the store with the exact expected payload, the evaluator's query
returned nothing. Its window is built with

```python
datetime.now().astimezone(local).strftime("...T%H:%M:%S+00:00")
```

which prints the local clock and labels it UTC. On a UTC machine -- which is
what upstream runs -- the label is true. Here it put the upper bound seven
hours in the past, so an entry written seconds earlier was outside the
window. `grade_task.google_cloud` now grades with `TZ=UTC`: upstream's
evaluator is authority on what passes, and the only thing wrong was the
clock it was handed.
