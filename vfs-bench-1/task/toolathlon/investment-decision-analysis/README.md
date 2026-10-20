# Investment decision analysis

Read `results.xlsx`, whose three worksheets are empty below their headers,
and build **three separate Google Sheets** named after them: year-end prices,
returns and the growth of $10,000 for NVDA and AAPL from 2020 to 2024; annual
revenue, year-end P/E and revenue growth; and a five-row scorecard that names
the better stock on each metric.

## NVDA's fiscal year

NVDA's fiscal year ends in late January, so the statement dated
`2023-01-29` covers February 2022 to January 2023 — and upstream's ground
truth calls that **2022**. AAPL, whose year ends in September, is inside its
calendar year.

This is upstream's own trap, not the fixture's: real Yahoo labels those
statements by period end exactly as the fixture does, the task statement says
nothing about fiscal years, and the sheet gives no worked example — the
`Fundamental Analysis` rows ship empty.

## The fixture is cheaper than the market

> The fixture this section describes was replaced on 2026-09-19 by an original Yahoo capture; see [Original capture](#original-capture--2026-09-19).

A four-year daily query returns about 260 bars per ticker where the market
had 1,006 sessions.

That is a consequence of how the capture is built.
`script/capture_fundamentals.py` recovers
what the answer sheet pins — ten year-end closes, eight annual income
statements, and the `.info` quotes — and nothing else, because nothing else
is recoverable from it. The days between year-ends are `author_prices.py`'s
synthetic series, 660 sessions of AAPL and NVDA reaching back to January 2024
after anchoring; the graded closes are unaffected, since a captured bar wins
its own date through `ON CONFLICT DO NOTHING` and December 2020 through
December 2023 hold no authored bars at all.

Both halves are in this task's own `shared/market/`, and the split between
them is the filename: `.captured` rows never move when the fixture is
anchored, because they are real quotes for named days. That replaced a pair
of exemption lists in the seeder keyed on `(symbol, date)` and
`(symbol, period_end)` — the second because a fiscal year end that had slid
five months names a different fiscal year, and a year-end P/E would then
divide one year's price by another year's earnings.

## What the ground truth pins, and what it does not

`investment_analysis_groundtruth.xlsx` pins year-end closes, annual revenue
and year-end P/E, and — because it also pins each year's *return* and
*growth rate* — the year before the first is recoverable too. Every constant
in the capture is checked back against the sheet:

    uv run python task/toolathlon/script/capture_fundamentals.py --check

The last three rows of the third worksheet are different: current P/E,
analyst target and upside, which `evaluation/realtime.py` recomputes from
`yf.Ticker(...).info` at grading time. That is the
[stock-build-position](../stock-build-position/README.md) shape — the
evaluator prices its own expected answer — so those fields are authored, and
chosen so the two tickers disagree on every row rather than handing the
"Better Stock" column three identical verdicts. See
[server/clients/README.md](../../../server/clients/README.md).

## A third fix to the mock Google Workspace server

The evaluator reads each sheet with `range='A:Z'`, a whole-column range with
no row numbers, and the mock answered `Unable to parse range: A:Z` — its
bare-range test wanted a digit after the column letters. Nothing could be
graded until it was fixed. It landed in
[mirage#762](https://github.com/strukto-ai/mirage/pull/762) with the two
[qfa](../quantitative-financial-analysis/README.md) found; review added a
fourth case there, because `updateCells` should honour a `fields` mask and
leave values alone when the mask names only formatting. The pin is
`f8be7c542`, the merge.

## Original Google tool CLI — 2026-09-13

The current interface is `google-sheet <original-tool-name>` with one JSON argument object. It invokes the pinned original MCP handlers and preserves their schemas, defaults and responses. The broad `gws` registration has been removed. The Sheets CLI has exactly 20 commands, including the original folder tools.

Live read/write and schema parity checks passed. `tests/parity.py` checks this CLI's commands against the server's tools on every run.

## Original capture — 2026-09-19

> The fixture this section describes was replaced on 2026-09-25 by live Yahoo; see [Live Yahoo](#live-yahoo--2026-09-25).

The reconstructed year-end bars, statements and quotes, and the authored
days between them, are gone. `shared/fixtures/yahoo/` holds the pinned
SDK's `history(period="max", auto_adjust=False)`, `info` and all six
statement tables for `NVDA` and `AAPL`, captured 2026-09-19, and
`shared/market/` derives 18,491 bars, 66 statements and the two quotes from
it. The five fiscal years Yahoo serves today reach back to NVDA's January
2022 and AAPL's September 2021, so every revenue and P/E cell the workbook
pins is computable from the fixture, and `capture_market.py verify` checks
each one, and every year-end close, against the answer sheet at the
grader's 3%. The manifest no longer anchors.

## Live Yahoo — 2026-09-25

Both arms and the grader now read Yahoo live, as upstream does, and the
capture is gone. The CLI, the MCP server and the evaluator's own
`yf.Ticker(...).info` all go through the one recording transport, and
nothing a run reads is kept. The capture held prices, quotes and statements
but no analyst ratings, so `get_recommendations` answered `[]` or an error
on both arms; live, it answers what Yahoo holds. The evaluator also needs
its Sheets shim, so `grade_task.py` runs the two from one combined
`sitecustomize`.
