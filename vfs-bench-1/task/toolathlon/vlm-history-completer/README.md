# vlm-history-completer

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `playwright_with_chunk`, `google_sheet`, `arxiv_local`, `huggingface`, `fetch`.

The original Directory of Generative AI workbook is captured with all five
worksheets. Original preprocessing copies it into a fresh fixture folder; the
original evaluator reads that same copy. Dates, compact numbers and hyperlinks
are retained. Hugging Face uses its original public remote MCP endpoint and
the separate `hf` CLI.

VFS exposes `web-search`, `browser`, `fetch`, `gws`, `arxiv-local`, `hf`. Use each command’s `--help` for its interface.
Browser tools retain their suffix: `browser_navigate` becomes `browser navigate`.

Setup and source verification:

```sh
uv run python -m server.mcp.setup_travel_video
uv run python -m server.mcp.setup_memory
npm ci --prefix vendor/mcp-remote
uv run python -m setup.final_lineage
uv run python setup/lineage.py
uv run dvc status
```

The source is an XLSX export plus public rendering captures, not an original
`spreadsheets.get(includeGridData=true)` capture. Exact formatting-response
fidelity therefore remains unverified. The seeder now leaves unstyled empty
cells unformatted, removing the 40,202 artificial format entries while
retaining real source styles, values, dimensions and hyperlinks. Guidance
uses the existing `gws sheets read` command for value ranges. The captured
XLSX and public rendering bytes are unchanged.

Original task files are read from pinned Git objects.

Evaluator SHA-256: `46adfb9b161478c1baec27948a6a2635b04de388e72233a8140e1ba9368c95b0`.

## Original Google tool CLI — 2026-09-13

The current interface is `google-sheet <original-tool-name>` with one JSON argument object. It invokes the pinned original MCP handlers and preserves their schemas, defaults and responses. The broad `gws` registration has been removed. The Sheets CLI has exactly 20 commands, including the original folder tools.

Live read/write and schema parity checks passed. `tests/parity.py` checks this CLI's commands against the server's tools on every run.
