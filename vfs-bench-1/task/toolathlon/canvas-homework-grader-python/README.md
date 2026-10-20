# canvas-homework-grader-python

Read Python homework attachments, execute the submissions and post the required grades to Canvas.

Both arms use the original Canvas service in a fresh E2B sandbox.
The `/canvas` mount provides live reads; the separate `canvas` CLI performs
service writes. The MCP arm runs the pinned original server and dependency tree.
The owned mail service runs in the same sandbox; `/mail` provides read-only
inspection and `emails` invokes the pinned original handlers for operations.

The snapshot contains the original Canvas PostgreSQL database, workspace and 149 original messages. Mail restoration checks raw MIME bytes, UIDs, dates and durable flags, including attachment bytes. The teacher sees the original course, six student enrollments and homework assignment. Grader reference data remains outside the agent workspace.

The task prompt is copied byte for byte from the pinned Toolathlon source.
DVC stage `capture-canvas-homework` records the capture and its source dependencies.
The source receipt records upstream input hashes, pinned service images and
artifact checksums. Before execution, the harness restores the snapshot and
compares API state hashes. It runs the original grader inside the sandbox and
deletes the sandbox after the run or a failure.

Use the existing [service setup](../canvas-art-quiz/README.md) and configure `E2B_API_KEY` and model credentials.
Run the arms sequentially because their local service ports are fixed:

```sh
uv run python agent/run_agent.py toolathlon/canvas-homework-grader-python --tools mcp
uv run python agent/run_agent.py toolathlon/canvas-homework-grader-python --tools vfs
uv run dvc status
```

For a deliberate fresh capture, use
`uv run python -m task.toolathlon.script.capture_canvas canvas-homework-grader-python`.
The producer refuses to overwrite an existing capture.

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
