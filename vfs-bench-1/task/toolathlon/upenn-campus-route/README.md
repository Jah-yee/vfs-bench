# upenn-campus-route

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `filesystem`, `terminal`, `google_map`, `fetch`.

Live runs require `GOOGLE_MAPS_API_KEY` in `.env.development`. Enable the APIs
used by the original server (Places, Directions, Distance Matrix, Geocoding
and Elevation). Setup stops before the agent starts when the key is missing.

VFS exposes `web-search`, `fetch`, `google-map`. Use each command’s `--help` for its interface.
The new service CLIs preserve original tool names and JSON schemas and
invoke their handlers directly, without an MCP client.

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

A Mirage Pyodide bug made `python3 -m json.tool /work/upenn_route_plan.json`
exit 1 with the blank diagnostic `python3:`. The failure also reproduced
with RAM and disk mounts on the then-current Mirage main.
`json.tool` closes its output stream; Mirage's reusable Pyodide runner then
flushed that closed capture stream, let the resulting exception escape, and
formatted its empty message. Mirage PR
[#1058](https://github.com/strukto-ai/mirage/pull/1058) fixes the general
closed-stream handling defect and resolves
[#1057](https://github.com/strukto-ai/mirage/issues/1057).
