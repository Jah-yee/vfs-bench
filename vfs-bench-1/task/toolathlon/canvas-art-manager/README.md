# canvas-art-manager

Create and publish the courses assigned to the registrar, enroll their instructors, publish announcements and attach syllabi from the original workspace.

The frozen capture contains the original Canvas PostgreSQL database, generated mailbox and workspace files. It comes from the original course seeder and inbox generator; it contains benchmark accounts, not a live university account. Each arm restores the capture in a fresh E2B sandbox and runs the original grader there.

The original Canvas and email MCP servers retain their pinned dependencies.
VFS uses the existing `/canvas` and `/mail` mounts, separate `canvas` and
`emails` CLIs, and `/work` for files. Both CLIs invoke the pinned original
handlers for service operations.

`capture-canvas-art-manager` in `dvc.yaml` records the fixture dependencies. The
`papers-forms-lineage` stage checks original task text, source receipts,
server locks, artifact hashes and CLI timeouts against upstream.
See [setup and shared validation](../README.md#paper-forms-and-canvas-conversions).

```sh
uv run python agent/run_agent.py toolathlon/canvas-art-manager --tools mcp
uv run python agent/run_agent.py toolathlon/canvas-art-manager --tools vfs
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
