# Quantitative financial analysis

Create a Google Sheet `2025_Market_Data` with a worksheet `Jun-Jul_2025`,
put the unadjusted daily open, high, low, close and volume for Apple, Tesla,
Nvidia and Meta on every trading day in June and July 2025 into it in the
shape `example.csv` establishes, then write `Google Sheet : {url}` on the
Notion page `Quant Research` and comment on it.

168 rows and 1,176 cells, all of which have to reach a spreadsheet.

## The MCP arm was reading the live internet

Found here, fixed in the harness, and it affects more than this task.

Toolathlon's `terminal` server allows `curl` and `wget`, and its
`python_execute` local tool runs model-written code under `uv run` with the
host's environment. Both therefore had real network access, while the mirage
arm's runtimes have none at all.

[`agent/run_agent.py`](../../../agent/run_agent.py) now closes both doors:
`TERMINAL_COMMANDS` drops the six network commands from upstream's
`terminal.yaml`, and `airgapped_tool` wraps `python_execute` in proxy
settings that refuse every outbound connection while leaving localhost — the
mocks, the Notion fake, GreenMail, Postgres — reachable.

## Two fixes to the mock Google Workspace server

Both are fidelity gaps in mirage's gws mock (`integ/server/gws_server.ts`
at the time; `integ/server/gws/` since the kit split it up), both were found by
this task, and both landed in
[mirage#762](https://github.com/strukto-ai/mirage/pull/762) with cases in
`integ/cli/gws.json` that fail without them.

- **A quoted worksheet name did not resolve.** `parseA1` stripped the quotes
  around `'Jun-Jul_2025'` only when a `!A1:G9` part followed, and gspread
  always quotes and sends the bare name for a whole worksheet. So the
  evaluator could not read the sheet at all, whichever arm wrote it, and the
  task was ungradeable. Quoting is now handled before the `!` split, doubled
  apostrophes included.
- **`updateCells` was unimplemented.** It is how a caller shortens a sheet it
  previously wrote longer; the mock answered `Unsupported request: updateCells`
  and the stale rows stayed.

`autoFill` is still unimplemented. That is left alone: it is an inference request, not storage.

Two other divergences are documented rather than fixed. `spreadsheets.create`
ignores the `sheets[]` array the real API honours, so a new spreadsheet always
arrives as one tab called `Sheet1` — [`vfs/SKILL.md`](vfs/SKILL.md) says so,
which puts both arms on the same two-step, since `mcp-google-sheets` splits
`create_spreadsheet` and `create_sheet` anyway. And **the mock does not
evaluate formulas**; on real Sheets a `GOOGLEFINANCE` formula would populate
something, though matching 1,176 cells to 0.1% against a stored capture is
another matter.

## The prices are real, and they came from the task

> The fixture this section describes was replaced on 2026-09-19 by an original Yahoo capture; see [Original capture](#original-capture--2026-09-19).

This is the one ported task whose evaluator compares against remembered
quotes rather than pricing its own expected answer, so
`script/author_prices.py`'s generated series cannot serve
it. It does not have to: upstream ships
`groundtruth_workspace/groundtruth_data.csv`, 168 real bars for these four
tickers over exactly these two months, and
`script/capture_prices.py` reads that back into
`yf.stock_prices`. The fixture is therefore the ground truth, recovered from
the task rather than invented for it, and `--check` re-verifies the committed
file against upstream. It is also the whole of this task's fixture: 168 rows,
no generated series beside them, and no anchoring, because the two months are
named in the prompt.

That took a change of shape. While every yahoo task shared one set of tables,
the generated AAPL, META and NVDA series slid across June and July 2025 as
they were anchored forward — dates that did not collide with the real bars but
interleaved between them, so a query for June returned 60 bars where the
market had 42. `seed.py` carried a `carve()` that dropped every generated bar
inside a month a capture owned, and the seams it left were read by
yahoo-analysis. Per-task fixtures removed the
need for it.

## Seeding

[`shared/seed_db.py`](shared/seed_db.py) stands in for upstream's two-part
preprocess: a Drive folder named `quantitative-financial-analysis` on the
mock, and the `Quant Research` page on mirage's Notion fake, seeded from
[`shared/notion_fixture.json`](shared/notion_fixture.json), which
[`shared/author_fixture.py`](shared/author_fixture.py) derived from
Toolathlon's own public template. Both ids go back to upstream's `files/`,
because its `token_key_session.py` and `evaluation/check_content.py` read
them from there.

Re-seeding before every run is not optional. `check_content` takes the
*first* `Google Sheet : {url}` on the page, which after a second run is the
previous run's sheet.

## Original Google tool CLI — 2026-09-13

The current interface is `google-sheet <original-tool-name>` with one JSON argument object. It invokes the pinned original MCP handlers and preserves their schemas, defaults and responses. The broad `gws` registration has been removed. The Sheets CLI has exactly 20 commands, including the original folder tools.

Live read/write and schema parity checks passed. `tests/parity.py` checks this CLI's commands against the server's tools on every run.

> The fixture this section describes was replaced on 2026-09-25 by live Yahoo; see [Live Yahoo](#live-yahoo--2026-09-25).

## Original capture — 2026-09-19

The rows recovered from the answer sheet are gone. `shared/fixtures/yahoo/`
holds the pinned SDK's `history(period="2y", auto_adjust=False)` and `info`
for `AAPL`, `TSLA`, `NVDA` and `META`, captured 2026-09-19, and
`shared/market/` derives 2,004 bars from it -- the task's two months and
the rest of two years, so a wider query answers as the service does.
`capture_market.py verify` compares every June and July 2025 cell against
`groundtruth_data.csv` at the grader's 0.1%.

## Live Yahoo — 2026-09-25

Both arms now read `AAPL`, `TSLA`, `NVDA` and `META` live, as upstream
does, and the capture is gone. The grader compares against the
task's committed answer sheet and reads no Yahoo itself.
