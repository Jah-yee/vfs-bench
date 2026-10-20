# Stock build position

Fifteen companies in `stock.xlsx`, $1M to allocate 4:3:3 across US, Hong Kong
and A-shares at today's opening prices, whole shares only and A-shares in
lots of 100. Fill in the ticker and the position size.

**The first task needing both halves of the workspace at once.** The fixture
and the answer are xlsx, which is a zip container, so it needs zlib and
therefore the `pyodide` runtime; the prices are a query over (ticker, date),
which no directory listing answers, so they come from the `yahoo-finance` CLI.
Neither half alone is enough, and the CLI is named by the task's own yaml as
`cli: ../../../../cli/toolathlon/travel-video.mjs:YAHOO` — see
[cli/toolathlon/travel-video.mjs](../../../cli/toolathlon/travel-video.mjs).

## The MCP arm was pricing in live FX

Toolathlon's `terminal` server allowed `curl` and its `python_execute` local
tool ran model-written code with the host's network, while the mirage arm's
runtimes have none.
[`agent/run_agent.py`](../../../agent/run_agent.py) now closes both doors; see
[quantitative-financial-analysis](../quantitative-financial-analysis/README.md#the-mcp-arm-was-reading-the-live-internet).

Closing them exposed a second problem, this one in the fixture, and it hit
**both** arms. The task converts at *today's* rate. `HKDUSD=X` and
`CNYUSD=X` are authored and anchored, so they run to today; `USDCNY=X` is
**pinned** — frozen, because `travel-exchange` and `invoice-org` name
calendar dates and want the rate used on them — so it stopped at the end of
the committed file and answered a five-day query with nothing. A ticker that
exists and has no recent data is not something the real API does.

> The fixture this section describes was replaced on 2026-09-19 by an original Yahoo capture; see [Original capture](#original-capture--2026-09-19).

This task's fixture now carries its own flat `USDCNY=X`, running to the end
of its own window and anchored forward with everything else in it, so the
rate answers a query about today. It costs nothing because the series is
flat by construction, and the level is the one `travel-exchange` recovered
rather than a second invention.

The seeder used to do this at run time, in an `extend_pinned()` that
repeated the last committed session forward through today. It existed
because one set of tables had to serve this task and the two that name a
calendar date; one fixture per task is what let the difference move into the
data instead.

> The Postgres shim this section describes was retired on 2026-09-25; see [Live Yahoo](#live-yahoo--2026-09-25).

## Grading needs the shim

The evaluator prices its own expected answer — `yf.Ticker(t).history(
period="1d")` for all fifteen tickers plus `HKDUSD=X` and `CNYUSD=X` — so it
has to read the same rows the agent did. Without `PYTHONPATH` pointing at the
shim it reaches the live API instead, and then no answer can pass whatever the
agent does.

```bash
uv run python server/seed/seed_task.py stock-build-position
AGENT_WORKSPACE=/tmp/sbp uv run python agent/run_agent.py \
    --task-dir task/toolathlon/stock-build-position --tools vfs

(cd submodule/Toolathlon && PYTHONPATH="$PWD/../redirect/yfinance" \
    PG_HOST=localhost PG_PORT=5433 PG_USER=eigent PG_PASSWORD=camel \
    PG_DATABASE=vfs_bench uv run --with psycopg2-binary -m \
    tasks.finalpool.stock-build-position.evaluation.main \
    --agent_workspace /tmp/sbp --res_log_file "$STUB")
```

This task's manifest declares `"anchor": "today"`: it asks for today's
opening price, and `period="1d"` becomes `date >= now() - 1 day`, which a
fixture committed months ago answers with nothing. `travel-exchange`, which
names a calendar date, declares no anchor and keeps its own rows where they
are — the two used to be the same table, and holding them apart inside it is
what the seeder carried three exemption lists for. See
[server/clients/README.md](../../../server/clients/README.md).

> The fixture this section describes was replaced on 2026-09-25 by live Yahoo; see [Live Yahoo](#live-yahoo--2026-09-25).

## Original capture — 2026-09-19

The authored and flat series are gone. `shared/fixtures/yahoo/` holds the
pinned SDK's `history(period="1y", auto_adjust=False)` and `info` for all
fifteen names in `stock.xlsx` and for nine FX spellings -- `HKDUSD=X`,
`CNYUSD=X`, `USDCNY=X`, `USDHKD=X`, `CNY=X`, `HKD=X`, `CNH=X`, `HKDCNY=X`
and `CNYHKD=X` -- captured 2026-09-19, and `shared/market/` derives 5,793
bars from it. Each exchange keeps its actual last session: 18 September for
Hong Kong and the mainland, 19 September for the FX pairs. `CNH=X` has no
history on Yahoo, only a latest quote, so it holds one bar here too. The
manifest no longer anchors: `history(period="1d")` reads the capture's last
session on both arms and in the grader.

## Live Yahoo — 2026-09-25

Both arms now read Yahoo live, as upstream does, and so does the
evaluator's `yf.Ticker(t).history(period="1d")`, through the same recording
transport as the agent's tools. Agent and grader price from the
same live service minutes apart, which is how upstream grades this task.
Before this, the MCP arm's Python in upstream's image (vfs-bench #72)
reached live Yahoo while its Yahoo tool served the capture.
