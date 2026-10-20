# notion-find-job

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `google_map`, `notion`, `emails`, `playwright_with_chunk`.

The original public Notion page, all database rows and child blocks are captured
under `shared/fixtures/`. Both surfaces use a fresh Notion fixture populated
from that capture. Mail, where required, stays in isolated local mailboxes.

Live runs require `GOOGLE_MAPS_API_KEY` in `.env.development`. Enable the APIs
used by the original server (Places, Directions, Distance Matrix, Geocoding
and Elevation). Setup stops before the agent starts when the key is missing.

VFS exposes `browser`, `google-map`, `notion`, `emails`. Use each command’s `--help` for its interface.
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
server. The captured hierarchy reproduces `Notion Eval Page` → `Job Finder` →
`Job Tracker`; the unchanged grader sees all 38 rows. Its author-specific
absolute mail-fixture path is absent in the pinned runtime, so the extra-inbox
check is skipped.
