# k8s-pr-preview-testing

The original Toolathlon task runs in a fresh E2B sandbox on both surfaces.
Browser MCP uses the original locked Playwright fork and arguments. The
separate browser CLI invokes that package's handlers: `browser_navigate`
becomes `browser navigate`; all remaining suffixes stay intact.

`browser --help` lists commands; `browser <command> --help` returns the
original argument schema. Pass arguments as one JSON object or pipe it
to `browser <command> -`. The browser session persists across calls. Command results contain the
original MCP text directly, so normal line-based shell piping works.

/work is E2B disk shared through Mirage's SSH mount. S3 retains the run
archive after grading. The browser and native commands see the same files.

The original cluster setup and grader run in that same sandbox. Git clones
the captured feature/pr-123 branch through its original GitHub URL, so both
arms receive identical repository bytes. The cluster, browser and terminal
share localhost. Source hashes and the Git bundle are tracked by DVC.

After repository setup, configure E2B and S3 credentials in .env.development.
Derive the browser lock and build the existing E2B template if needed:

```sh
uv run python -c "from server.mcp.setup_browser import derive; derive()"
uv run python server/kubernetes_template.py
uv run python agent/run_agent.py toolathlon/k8s-pr-preview-testing --tools mcp
uv run python agent/run_agent.py toolathlon/k8s-pr-preview-testing --tools vfs
```

The runtime installs the pinned Chromium and browser server inside E2B.
The local setup helper can also install them for development.

## Preflight

A separate E2B preflight passed original terminal cloning, browser CLI
help/navigation/snapshot, piped JSON, and visibility of native Python writes
through the SSH mount. It also passed the original grader with the original
reference report supplied after deployment. That verifies grader wiring,
not model performance. The checkout test checks the exact order-ID text,
not just a visible success message.

The Git preflight exposed a pinned Mirage S3/FUSE defect: cloning the same
11 KB bundle took 0.096 seconds on sandbox disk, but failed after 160.678
seconds on S3/FUSE with truncated pack files. Browser runs therefore use
SSH over the sandbox filesystem, with S3 retaining the final archive.
