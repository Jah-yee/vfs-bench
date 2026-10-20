# inter-final-performance-analysis

Original Toolathlon task at `9be8d8fe07a497b18ee61e3f2ae694e9797f39eb`.
The prompt, initial workspace and grader are unchanged. Both arms use the
original Serper handler and locked fetch/browser servers. The search, fetch and browser
CLIs preserve the original tool names and JSON arguments. Browser hosting
is local. Exact search/fetch requests share captured responses; new requests
and browser navigation use the live web.

The original public Sheet is captured with its source URL and hashes. Each
arm restores it into a separate local Mirage Sheets fixture, runs original
preprocessing and grades against that same fixture. The `/gd` mount is
scoped to the task folder; the `gws` CLI remains separate from the mount.

Original tool schema/response parity and service startup were checked with
temporary integration probes. Source hashes are covered by DVC; no test
files were added.

## Runtime review

Current source review confirms that `.gsheet.json` requests a complete
workbook with `includeGridData=true`. Both surfaces can request
values or metadata, but these defaults expose very different amounts of
text. The common 100,000-character harness cap does not make them equivalent.
A separate disposable-fixture probe populated the original reference CSVs and passed the unchanged grader; that is connectivity validation, not a model success.

Pyodide rejects `subprocess.run` calls used to invoke search and Sheets CLIs. This is a limitation of the configured Python runtime.

VFS guidance states that the Drive mount exposes `.gsheet.json` files, not CSV directories. The guidance also identifies Pyodide limitations and scopes JSON-argument instructions to search/browser/fetch CLIs.

## Original Google tool CLI — 2026-09-13

The current interface is `google-sheet <original-tool-name>` with one JSON argument object. It invokes the pinned original MCP handlers and preserves their schemas, defaults and responses. The broad `gws` registration has been removed. The Sheets CLI has exactly 20 commands, including the original folder tools.

Live read/write and schema parity checks passed. `tests/parity.py` checks this CLI's commands against the server's tools on every run.
