# Invoice org

Seven invoice PDFs in mixed currencies. Extract the amount, date and vendor
from each into `invoice_summary.csv`, convert every one to CNY at the rate on
its own invoice date, and write the grand total to `total_invoice.json`.

**zlib twice over.** The invoice streams are deflate-compressed and the wheel
that reads them is itself a zip, so this task cannot run on any Python-side
runtime; `pyodide` is the only one with zlib. The rates are the other half and
are not path-shaped — no listing names a rate on a date — so they come from
the `yahoo-finance` CLI, which runs the original Yahoo tools. See
[cli/toolathlon/travel-video.mjs](../../../cli/toolathlon/travel-video.mjs).

Four servers are mounted for what is a read-seven-files-and-add-them-up task:
`pdf-tools` (9), `filesystem` (14), `yahoo-finance` (10), `excel` (25).

## Which date is the invoice date

The brief asks for "the date" without saying which, but the ground truth is
not ambiguous: it is `DATE OF ISSUE` verbatim, blank where that field is
blank. The flight itineraries carry a second date, the flight leg:

| file | `DATE OF ISSUE` | flight leg | ground truth |
|---|---|---|---|
| flight_invoice.pdf | *(blank)* | 3DEC | `""`, unchecked |
| flight_invoice1.pdf | 2024-12-20 | 28DEC | 2024-12-20 |
| flight_invoice3.pdf | 2024-02-04 | 1MAR | 2024-02-04 |

flight_invoice1 and flight_invoice3 are CNY invoices whose `exchange_rate`
is 1.0, so the date feeds no arithmetic. No total the agent could compute
would disagree with it.

Nothing in the workspace is corrected for this. Telling the agent to prefer
the issue date would be writing the answer into the prompt, and the task is
upstream's.

## The two arms do not have the same reach

mirage's `python3` is sandboxed: no host filesystem, no network. Toolathlon's
`local-python-execute` and `run_command` have both. So an agent on that arm can
skip the fixture entirely.

The asymmetry is worth knowing, because a future task whose ground truth
cannot be reconstructed offline would turn it decisive.

## The rates are pinned to this task's ground truth

> The fixture this section describes was replaced on 2026-09-19 by an original Yahoo capture; see [Original capture](#original-capture--2026-09-19).

`total_invoice.json` states the four rates it expects, so the fixture supplies
exactly those on exactly those dates. That the flat rate had been close enough
for the per-rate tolerance was not enough: the total carries a separate 10 CNY
allowance, and the largest invoice is 425 USD, so a 0.033 error on one rate
became 14.20 CNY and fails the total. See
`script/author_prices.py`.

```bash
uv run python server/seed/seed_task.py invoice-org
AGENT_WORKSPACE=/tmp/io uv run python agent/run_agent.py \
    --task-dir task/toolathlon/invoice-org --tools vfs
```

The evaluator compares against a static `groundtruth_workspace` and calls no
market API, so unlike `stock-build-position` it does not need the shim.

## Original capture — 2026-09-19

> The fixture this section describes was replaced on 2026-09-25 by live Yahoo; see [Live Yahoo](#live-yahoo--2026-09-25).

The pinned rates are gone. `shared/fixtures/yahoo/` holds the pinned SDK's
`history(period="5y", auto_adjust=False)` and `info` for `SGDCNY=X`,
`USDCNY=X`, `CNY=X`, `SGD=X`, `USDSGD=X` and `CNYSGD=X`, captured
2026-09-19, and `shared/market/` derives 6,506 bars from it.
`capture_market.py verify` checks the rate nearest each invoice date against
`total_invoice.json` at the grader's 0.05; two of the dates fall on a
weekend and resolve to a neighbouring session, as they do for the original
server's `find_nearest`.

## Live Yahoo — 2026-09-25

Both arms now read the SGD and USD rates live, as upstream does, and the
capture is gone. The grader compares against the task's
committed answer and reads no Yahoo itself.
