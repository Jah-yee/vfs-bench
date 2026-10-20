# fillout-online-forms

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `playwright_with_chunk`, `memory`, `filesystem`.

This task uses the real Google Forms browser UI. Set
`GOOGLE_APPLICATION_CREDENTIALS` to the benchmark OAuth credential JSON with
Forms and Drive access. The original form creator and response grader run in
a private source tree. The original memory file is shared by the locked memory
MCP server, the separate memory CLI, and `/work/memory/memory.json`.

VFS exposes `browser`, `memory`. Use each command’s `--help` for its interface.
The new service CLIs preserve original tool names and JSON schemas and
invoke their handlers directly, without an MCP client.
Browser tools retain their suffix: `browser_navigate` becomes `browser navigate`.

Setup and source verification:

```sh
uv run python -m server.mcp.setup_travel_video
uv run python -m server.mcp.setup_memory
uv run python -m setup.final_lineage
uv run python setup/lineage.py
uv run dvc status
```

## Validation

The original memory fixture was read identically through MCP and the CLI;
a CLI mutation was visible through MCP. All nine memory tool schemas match.
The original browser starts with a fresh context. Live form creation, browser
submission and original response grading passed for both surfaces.
