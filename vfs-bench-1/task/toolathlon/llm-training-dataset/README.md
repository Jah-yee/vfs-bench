# llm-training-dataset

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

Execution capabilities differ: MCP retains the original native Python
tool, while the VFS workspace selects Pyodide and separate service CLIs.
Missing native processes/packages therefore represent an environment
difference chosen by this benchmark, not an unexpected Mirage failure.

The VFS guidance notes that the Drive mount exposes `.gsheet.json` files, not CSV directories. The guidance also identifies Pyodide limitations and scopes JSON-argument instructions to search/browser/fetch CLIs.

## Original Google tool CLI — 2026-09-13

The current interface is `google-sheet <original-tool-name>` with one JSON argument object. It invokes the pinned original MCP handlers and preserves their schemas, defaults and responses. The broad `gws` registration has been removed. The Sheets CLI has exactly 20 commands, including the original folder tools.

Live read/write and schema parity checks passed. `tests/parity.py` checks this CLI's commands against the server's tools on every run.
