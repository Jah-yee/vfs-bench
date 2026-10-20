# subway-planning

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `google_map`, `filesystem`, `playwright_with_chunk`, `fetch`.

Live runs require `GOOGLE_MAPS_API_KEY` in `.env.development`. Enable the APIs
used by the original server (Places, Directions, Distance Matrix, Geocoding
and Elevation). Setup stops before the agent starts when the key is missing.

VFS exposes `web-search`, `browser`, `fetch`, `google-map`. Use each command’s `--help` for its interface.
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

Full MCP and VFS startup passed, including original tool discovery, fixture
initialization and live Maps requests. The 7 Maps schemas match their original
server.
