# identify-all-songs

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `filesystem`, `youtube-transcript`, `playwright_with_chunk`, `fetch`.

VFS exposes `web-search`, `browser`, `fetch`, `youtube-transcript`. Use each command’s `--help` for its interface.
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

The transcript server and separate CLI use the same pinned upstream handlers; the local browser uses the original Playwright fork. Video, subtitle and browser access remain live.
Original task files are read from pinned Git objects.
