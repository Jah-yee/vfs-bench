# shopping-helper

Both surfaces run the original Toolathlon task with a browser in a local Docker container.
Browser MCP uses the original locked Playwright fork and arguments. The
separate browser CLI invokes that package's handlers: `browser_navigate`
becomes `browser navigate`; all remaining suffixes stay intact.

`browser --help` lists commands; `browser <command> --help` returns the
original argument schema. Pass arguments as one JSON object or pipe it
to `browser <command> -`. The browser session persists across calls. Command results contain the
original MCP text directly, so normal line-based shell piping works.

`/work` mounts the local run directory. Browser downloads and uploads use
that same directory. Only that arm's workspace is mounted into its container.

The two initial JSON files are copied from upstream. The unchanged grader
reopens live Amazon pages; access errors and changing prices remain part
of this live task and are not replaced with invented product fixtures.

After repository setup, start Docker and install the locked browser and configure model
credentials in .env.development. This task needs no E2B or S3 credentials:

```sh
uv run python -m server.mcp.setup_browser
uv run python agent/run_agent.py toolathlon/shopping-helper --tools mcp
uv run python agent/run_agent.py toolathlon/shopping-helper --tools vfs
```

The original grader runs locally with the same locked browser. The local
container uses upstream's root-user launch handling. Its image ID and npm
lock hash are recorded with each run.

Integration checks passed for all 31 schemas, original MCP/CLI text,
validation errors, JSON stdin, line-based piping, file URLs, uploads,
screenshots and downloads shared with VFS. The local browser reached a
public website and could not read the host repository outside its mount.
This integration probe used no E2B or S3 credentials. No test files were added.

## Browser access audit — 2026-09-10

The original task has no preprocessor or saved browser login. It starts
from example.json and recommend.json with an isolated browser. The grader
creates its own session and performs its original locale/currency warm-up;
that is not a hidden agent setup step.

The CLI's effective configuration equals the original Commander-parsed
configuration. In one E2B sandbox, MCP and CLI also produced identical
request headers and browser fingerprints and retained cookies/localStorage
across calls.

The current policy runs non-Kubernetes browsers locally on both surfaces.
Only Kubernetes tasks place their browser in E2B beside the cluster.

One presentation discrepancy was corrected: CLI results used a JSON
envelope with escaped newlines, while MCP delivered the text blocks
directly. The CLI now returns those same text blocks. This affects
readability and shell piping, not the HTTP response from Amazon.
