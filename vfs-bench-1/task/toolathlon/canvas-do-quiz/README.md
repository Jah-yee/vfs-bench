# canvas-do-quiz

Complete the student’s unfinished Canvas quizzes.

Both arms restore the same captured original seed in fresh E2B sandboxes.
The Canvas mount supplies live reads; the separate CLI supplies writes.
The MCP server and its dependency tree are pinned to the upstream baseline.

The capture contains the original courses, student identity, quizzes,
initial attempts and date-updated private course configuration.

`capture-canvas-do-quiz` in `dvc.yaml` links the fixture to the original task,
seeder/grader files, service images and capture code. `source.json` records
upstream file hashes and artifact checksums. The harness validates restored
API state and runs the original grader in the sandbox before cleanup.

Source/artifact checks and DVC pass; no test files were added.

Use the existing [service setup](../inventory-sync/README.md) with
`E2B_API_KEY`. Run the arms sequentially because the native service ports
are fixed:

```sh
uv run python agent/run_agent.py toolathlon/canvas-do-quiz --tools mcp
uv run python agent/run_agent.py toolathlon/canvas-do-quiz --tools vfs
uv run dvc status
```

The original preprocessor sets exam and quiz dates to tomorrow. Recapture
through the existing `capture-canvas-do-quiz` DVC stage when that window
expires; do not patch captured deadlines or weaken snapshot comparisons.
DVC hashes alone do not detect an expired time window.

Allow a newly generated capture to be at least ten minutes old before its
first restore. Native Canvas counts elapsed enrollment activity between
reads 2–10 minutes apart; a restore during that interval changes
`total_activity_time` even when no task content changed. The pinned image's
`app/models/enrollment/recent_activity.rb` confirms these thresholds.
Snapshot validation remains unchanged, including its existing exclusion
of read-induced `last_activity_at`.

## Current CLI and lineage

`canvas` now invokes the pinned original tool handlers directly, without an
MCP client. Commands drop the `canvas_` prefix and retain the original
schemas, pagination, defaults and response text. Use `canvas --help` and
`canvas <command> --help`. The filesystem mount still enumerates complete
REST collections independently of CLI pagination. Python is for processing
files and data; invoke service commands directly in the shell.

The `service-mcp-tools` DVC stage installs the original dependency locks and
derives `vendor/canvas-mcp/tools.json` and `source.json`. Both arms verify
the recorded tool implementation and schema hashes before startup. Existing
fixture captures retain their DVC source links.

`canvas submit-quiz-answers` now invokes the original handler, which
constructs the answer POST and completes the attempt. The local MCP/CLI
parity probe verified identical responses and the same two POST requests.

The local REST client was fixed in `cf07fde` to bound error bodies and
discard HTML error pages. A transport probe fed it a 1.5 MB HTML 404 and
received only the 21-character `canvas 404: Not Found` error.

The native fixture bytes are unchanged. Restore rebuilds the public schema
to avoid stale partition cleanup failures. Snapshot comparisons exclude the
read-induced enrollment `last_activity_at`; API responses retain it.

The original preprocessor refreshed the deadline to `2026-09-12T23:59:00Z`.
Its course configuration changed only `exam_time` and `due_at`; question
configuration, original source hashes and dependency pins were preserved.
The existing DVC capture stage regenerated the database, API snapshot and
workspace/private archives. Artifact checksums and all DVC lock edges pass.

## Upstream quiz-retry limitation

The pinned original Canvas client always sends `attempt: 1` when it saves
answers and completes a quiz. Its submit-tool schema does not accept an
attempt number. Canvas can therefore start attempt 2 for a quiz that permits
multiple attempts, but the next submit call addresses the completed first
attempt and Canvas returns `attempt 1 can not be modified`.

This affects both arms: MCP runs that client directly, and the VFS `canvas`
command invokes the same original handler. The restored service is the pinned
Canvas LMS container with the captured upstream database, so this is not a
fixture-emulation or Mirage error.

Native Canvas can also return quiz-attempt HTTP 500 errors. The server log
reports a missing `quiz_submission_events_2026_9` table, and the original
MCP client contains a recovery path for this class of response.
