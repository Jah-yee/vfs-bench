# canvas-arrange-exam

Build the exam schedule from course announcements and mail.

Both arms restore the same captured original seed in fresh E2B sandboxes.
The Canvas mount supplies live reads; the separate CLI supplies writes.
The MCP server and its dependency tree are pinned to the upstream baseline.

The capture contains 12 original courses, announcements, exam emails, the original workbook and private course configuration. The task’s fixed January 2025 date remains unchanged.

`capture-canvas-arrange-exam` in `dvc.yaml` links the fixture to the original task,
seeder/grader files, service images and capture code. `source.json` records
upstream file hashes and artifact checksums. The harness validates restored
API state and runs the original grader in the sandbox before cleanup.

Source/artifact checks and DVC pass; no test files were added.

Use the existing [service setup](../inventory-sync/README.md) with
`E2B_API_KEY`. Run the arms sequentially because the native service ports
are fixed:

```sh
uv run python agent/run_agent.py toolathlon/canvas-arrange-exam --tools mcp
uv run python agent/run_agent.py toolathlon/canvas-arrange-exam --tools vfs
uv run dvc status
```

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
fixture captures retain their DVC source links and bytes.

The native fixture bytes are unchanged. Restore rebuilds the public schema
to avoid stale partition cleanup failures. Snapshot comparisons exclude the
read-induced enrollment `last_activity_at`; API responses retain it.
