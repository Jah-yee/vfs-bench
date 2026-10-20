# latex-prompt-box

Edit the existing paper’s appendix TODO with the codebase’s two prompts using the reference paper’s LaTeX box style.

The original `files.tar.gz` and `codes.tar.gz` are extracted and removed before execution, matching the original preprocessor. Both arms receive the unchanged LaTeX project and codebase. The reference paper’s public arXiv source is read live on both arms, and each run records the request with its time and body hash; no reference answer is supplied to either arm.

MCP uses the original one-tool arXiv LaTeX server and dependency lock. The separate `arxiv-latex get-paper-prompt` CLI invokes that same handler and returns its LaTeX text on stdout. Files remain under `/work`; backend caches and logs are private. No E2B or additional API credentials are needed.

The
`papers-forms-lineage` stage checks original task text, source receipts,
server locks, artifact hashes and CLI timeouts against upstream.
See [setup and shared validation](../README.md#paper-forms-and-canvas-conversions).

```sh
uv run python agent/run_agent.py toolathlon/latex-prompt-box --tools mcp
uv run python agent/run_agent.py toolathlon/latex-prompt-box --tools vfs
```

## Terminal and cwd alignment

For this task only, VFS shell output now uses the original MCP terminal's
8,192-character stdout cap, 2,048-character stderr cap and truncation marker.
The values come from the pinned upstream terminal configuration. Direct
`arxiv-latex get-paper-prompt` calls retain the original service response;
these display caps do not truncate pipes or redirected files. Dumps record raw output
and the exact output returned to the model separately.

Each shell call starts in `/work`, matching the original terminal's fresh
process. Mirage's existing per-call cwd fork isolates parallel calls.
Mirage `f051662d69` also passes shell cwd to Pyodide and restores interpreter
cwd after success or failure. The shared TypeScript implementation serves
Node and browsers; interpreter request fields are mirrored in Python.

Validation covers exact truncation against the original handler, concurrent
disk reads, full pipelines/redirection, and relative Python reads/writes.
Mirage's 17 Pyodide integration cases pass. The existing task parity runner
has no LaTeX cases; the direct shell probe supplies the task-specific check.
