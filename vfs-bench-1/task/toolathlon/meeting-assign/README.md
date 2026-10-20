# meeting-assign

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `fetch`, `emails`, `playwright_with_chunk`, `filesystem`.

The original `files/files.tar.gz` is served at `localhost:30137`, including
inside the local browser container. The agent receives the original `format.md`.
The original sender and receiver identities use a fresh local mail service.

VFS exposes `web-search`, `browser`, `fetch`, `emails`. Use each command’s `--help` for its interface.
Browser tools retain their suffix: `browser_navigate` becomes `browser navigate`.

Setup and source verification:

```sh
uv run python -m server.mcp.setup_travel_video
uv run python -m server.mcp.setup_memory
uv run python -m setup.final_lineage
uv run python setup/lineage.py
uv run dvc status
```

Original task files are read from pinned Git objects.

Evaluator SHA-256: `9f1c2b9a6669d12e4e2a9eb1bef32486bec951b81b2244738829e882838a3150`.
