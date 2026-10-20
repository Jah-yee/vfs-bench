# canvas-new-students-notification

Enroll the missing students in Introduction to AI-8 and send them individual Canvas messages.

Both arms use the original Canvas service in a fresh E2B sandbox.
The `/canvas` mount provides live reads; the separate `canvas` CLI performs
service writes. The MCP arm runs the pinned original server and dependency tree.

The snapshot contains the original Canvas PostgreSQL database and student-list workspace. It retains the 504 synthetic account users, course enrollments, assignments and submissions. The original admin account can list account courses even when its own course list is empty.

The task prompt is copied byte for byte from the pinned Toolathlon source.
DVC stage `capture-canvas-notification` records the capture and its source dependencies.
The source receipt records upstream input hashes, pinned service images and
artifact checksums. Before execution, the harness restores the snapshot and
compares API state hashes. It runs the original grader inside the sandbox and
deletes the sandbox after the run or a failure.

Use the existing [service setup](../canvas-art-quiz/README.md) and configure `E2B_API_KEY` and model credentials.
Run the arms sequentially because their local service ports are fixed:

```sh
uv run python agent/run_agent.py toolathlon/canvas-new-students-notification --tools mcp
uv run python agent/run_agent.py toolathlon/canvas-new-students-notification --tools vfs
uv run dvc status
```

For a deliberate fresh capture, use
`uv run python -m task.toolathlon.script.capture_canvas canvas-new-students-notification`.
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

## Validation

The earlier live fixture check passed the original grader after enrollment and conversation writes.

The current adapter review found a concrete pagination mismatch. Upstream
`canvas_list_account_users` defaults to, and caps results at, 20 users per
page. Its recorded call returned 6,162 characters including navigation.
The previous `canvas list accounts/1/users` called `ServiceClient.list`, which defaults
to 100 per page and follows every page, collecting all 504 users before the
harness truncates output. It also overwrites an explicit `page` with its
loop starting at one; a temporary two-page HTTP fixture reproduced this.
This is a benchmark CLI/client issue, not a Canvas mock or Mirage bug.
The CLI now uses the original paginated handler, so it preserves the
requested page and 20-user cap. The mount retains complete traversal. A
local parity probe compared MCP and CLI responses and HTTP requests for
page 2 with `per_page=100`; both requested only page 2 at 20 users.
