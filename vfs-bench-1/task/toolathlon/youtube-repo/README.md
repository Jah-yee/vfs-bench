# youtube-repo

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `youtube`, `youtube-transcript`, `filesystem`, `fetch`, `github`.

Live runs require `YOUTUBE_API_KEY` with YouTube Data API access. Metadata
requests are cached by exact request for both arms. Transcript availability
and YouTube access restrictions remain upstream service constraints.

VFS exposes `web-search`, `fetch`, `youtube`, `youtube-transcript`, `gh`. Use each command’s `--help` for its interface.
The new service CLIs preserve original tool names and JSON schemas and
invoke their handlers directly, without an MCP client.

Setup and source verification:

```sh
uv run python -m server.mcp.setup_travel_video
uv run python -m server.mcp.setup_memory
uv run python -m server.mcp.setup_github
uv run python -m setup.final_lineage
uv run python setup/lineage.py
uv run dvc status
```

## Validation

Full MCP and VFS startup passed, including original tool discovery and
fixture initialization. Live YouTube Data API requests now pass with the
configured key. The 9 YouTube schemas match their original server.
