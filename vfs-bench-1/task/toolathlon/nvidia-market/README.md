# nvidia-market

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `yahoo-finance`, `filesystem`, `terminal`, `playwright_with_chunk`, `excel`, `fetch`.

The original Yahoo server and its dependency lock are reused. Both arms
read the original SDK live, and nothing a run reads is kept. Public
web/browser reads remain live.

VFS exposes `web-search`, `browser`, `fetch`, `yahoo-finance`. Use each command’s `--help` for its interface.
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

Original task files are read from pinned Git objects.

Evaluator SHA-256: `9c5cc9fe8717b948145ca1132a93ae05df7239a9635a4b347dfdf09703b6b8b6`.

## Live data — 2026-09-19

Every Yahoo call is answered by the original SDK live on both arms, as
upstream's runner answers it, and nothing a run reads is kept; each run's
record names every request with its time and response hash. The grader's
truth names quarter-end closes, which Yahoo serves split-adjusted and
unchanged, and balance-sheet share counts at dates that Yahoo's quarterly
statements have mostly stopped serving, as upstream's own notes say. The
13F holder tables the task also needs never came from Yahoo and are read
through the browser.
