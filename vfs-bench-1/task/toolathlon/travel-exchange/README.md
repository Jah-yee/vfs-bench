# Travel exchange

Seven people travelled to Turkey in 2025 and exchanged currency on 5 June.
Read every expense file in the workspace, convert each traveller's costs to
CNY at the rates actually used, and fill `calculation.json`.

**The first task here where market data is the fixture**, so it is worth being
precise about what is shared. Upstream's yahoo-finance server does not call
Yahoo: a local `yfinance.py` shadows the installed package and routes
`yf.Ticker(...)` through `pg_adapter` to Postgres. The mirage arm reads the same
rows through the `yahoo-finance` CLI, and the evaluator — which prices its own expected
answer — is put on them too with `PYTHONPATH=redirect/yfinance`. All three agree
before either arm runs; see [server/clients/README.md](../../../server/clients/README.md).

```bash
uv run python server/seed/seed_task.py travel-exchange
uv run python agent/run_agent.py toolathlon/travel-exchange --tools vfs
uv run python agent/run_agent.py toolathlon/travel-exchange --tools mcp
```

> The fixture this section describes was replaced on 2026-09-19 by an original Yahoo capture; see [Original capture](#original-capture--2026-09-19).

This task's manifest declares a `market` fixture **without** `"anchor"`. It
asks for the rate on a named date, 5 June 2025, and anchoring moves every
date forward to make `period="1d"` resolve — which is what
`stock-build-position` needs and what this task must not have. One shared
table could not give both tasks what they needed; one fixture per task can,
and the manifest is where the difference is written down.

> The fixture this section describes was replaced on 2026-09-25 by live Yahoo; see [Live Yahoo](#live-yahoo--2026-09-25).

## Original capture — 2026-09-19

The pinned flat rates are gone. `shared/fixtures/yahoo/` holds the pinned
SDK's `history(period="5y", auto_adjust=False)` and `info` for the four CNY
pairs and for `CNY=X`, `EUR=X`, `TRY=X`, `SGD=X` and `EURUSD=X`, captured
2026-09-19, and `shared/market/` derives 10,406 bars from it. Yahoo
carries no history for `TRYCNY=X`, only a latest quote, so the lira rate on
5 June 2025 is a cross through `CNY=X` and `TRY=X` here as it is on the
live service; `capture_market.py verify` checks all four rates for that day
against `calculation.json` at the grader's 0.1.

## Live Yahoo — 2026-09-25

Both arms now read the rates live, as upstream does, and the capture is
gone. The grader compares against the task's committed answer
and reads no Yahoo itself.
