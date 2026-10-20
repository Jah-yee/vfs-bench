# gdp-cr5-analysis

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

## Fixture limitations

These fixture limitations were observed:

- The MCP `search_spreadsheets` query uses `(name contains ... or fullText contains ...)`, which the Drive fake rejects.
- The VFS `repeatCell` request successfully set `PERCENT` with `0.00%`, but `server/fakes/sheet_formats.py` returned raw fractions on formatted reads. For example, `0.994365515905266` remained that string instead of `99.44%`; the unchanged grader therefore compared the wrong scale. The same renderer lacks the requested `#,##0.00` format.
- Spreadsheet creation ignored VFS's requested initial tab and returned `Sheet1`.
- The fixture rejected `autoResizeDimensions`.

The current fixture preserves the captured display values and ID shape; both CLI and mount use the original task folder. A temporary probe verified both creation paths and all 229 captured numeric display strings through the original MCP.

## Runtime review

Mirage's overflow saver once resubmitted large output as base64 stdin in a JSON request, which failed above 1 MiB. The current Mirage pin `8bba6503a9` includes the fix in [PR #1051](https://github.com/strukto-ai/mirage/pull/1051). The runner uploads stdin as multipart bytes. Live Python and TypeScript daemon checks passed on RAM and disk, in foreground and background, with grep/save/hash round trips above 1 MiB. Replaying the exact GDP output and a 3,161,900-byte version through the Toolathlon runner preserved every byte and delivered the overflow notice.

Toolathlon now saves complete output before applying upstream's 100,000-character cap. Its workspaces retain command timeouts without Mirage's default line caps; explicit task overrides remain intact. The MCP adapter copies upstream's serialization and both truncation passes, and local output-reader tools receive upstream's cap too. Temporary probes compared the model-visible text and saved files against the pinned upstream functions, including Unicode, multiple content blocks and boundary sizes. These changes apply to Toolathlon only.

VFS guidance states that the Drive mount exposes `.gsheet.json` files, not CSV directories. The guidance also identifies Pyodide limitations and scopes JSON-argument instructions to search/browser/fetch CLIs.

## Original Google tool CLI — 2026-09-13

The current interface is `google-sheet <original-tool-name>` with one JSON argument object. It invokes the pinned original MCP handlers and preserves their schemas, defaults and responses. The broad `gws` registration has been removed. The Sheets CLI has exactly 20 commands, including the original folder tools.

Live read/write and schema parity checks passed. `tests/parity.py` checks this CLI's commands against the server's tools on every run.
