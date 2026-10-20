# notion-movies

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `playwright_with_chunk`, `notion`, `fetch`.

The original public Notion page, all database rows and child blocks are captured
under `shared/fixtures/`. Both surfaces use a fresh Notion fixture populated
from that capture. Mail, where required, stays in isolated local mailboxes.

VFS exposes `web-search`, `browser`, `fetch`, `notion`. Use each command’s `--help` for its interface.
Browser tools retain their suffix: `browser_navigate` becomes `browser navigate`.

Setup and source verification:

```sh
uv run python -m server.mcp.setup_travel_video
uv run python -m server.mcp.setup_memory
uv run python -m setup.final_lineage
uv run python setup/lineage.py
uv run dvc status
```

Full mounted page JSON includes metadata, properties, rendered content and
blocks, whereas the MCP database query returns page properties without
fetching those child blocks.

Original task files are read from pinned Git objects.

Evaluator SHA-256: `f240d8b53abfd52401d760757026953edafa2cdd8b9d01ed430e8780817d7277`.
