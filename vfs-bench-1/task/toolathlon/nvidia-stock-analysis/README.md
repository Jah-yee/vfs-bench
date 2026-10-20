# nvidia-stock-analysis

Original Toolathlon ownership and market-trend workbook task. Both arms
receive the original `data.txt`, `tips.txt`, and `results_template.xlsx`.
The original grader checks the resulting `results.xlsx`.

MCP runs the original Yahoo Finance, filesystem, terminal, Excel and
Playwright servers. VFS uses the separate `yahoo-finance` and `browser` CLIs plus
Python/openpyxl over `/work`. The browser runs in a local Docker container
and shares the run directory. No E2B or additional service credentials are
needed; model credentials and the local fixture stack are still required.

The task declares an MCP server named `web_search`, but the pinned upstream
has no such server configuration. Its own manager warns and skips that
name. This conversion preserves that behavior; it does not add a search
provider. Public websites remain accessible through the browser.

> The fixture this section describes was replaced on 2026-09-25 by live Yahoo; see [Live Yahoo](#live-yahoo--2026-09-25).

## Market capture and lineage

Yahoo responses were captured on 2026-09-10 at 08:41 UTC using the pinned
Yahoo environment. The capture contains 6,950 historical daily bars, the
stock profile, six holder tables and six financial statements. The shared
Postgres fixture is derived from those responses. Named indices and date
types are retained so holder output matches the original MCP serialization.

`shared/fixtures/yahoo/source.json` records capture time, dependency-lock
hash, original task/input/grader hashes and the compressed response hash.
DVC tracks `capture-nvidia`, `derive-nvidia`, `ask@nvidia-stock-analysis`
and `nvidia-lineage`. Dates are not shifted and grader answers are never
used to populate market data. This capture does not replace the older
reconstructed fixtures in other market tasks.

The unchanged upstream grader uses a fixed June 2026 snapshot for Sheet1.
The current Yahoo quarterly balance sheet no longer contains every
historical shares-outstanding value requested by the task. Browser research
can supplement those values; the conversion does not fill them from the
grader. Sheet2 and Sheet3 are graded against the same captured holder data
that both arms receive.

## Run

After repository setup, start Docker and configure model credentials:

```sh
uv run python -m server.mcp.setup_browser
uv run python agent/run_agent.py toolathlon/nvidia-stock-analysis --tools mcp
uv run python agent/run_agent.py toolathlon/nvidia-stock-analysis --tools vfs
```

Integration checks started all five original MCP servers and compared all
six holder tables, all six financial statements and a historical price
through MCP and the actual Mirage CLI. Holder responses also matched the
captured table serialization. No test files were added.

Two existing launcher defects were corrected: the Yahoo CLI now resolves
shared market adapters during direct file execution, and Excel's log is
redirected from its read-only installation to the run's scratch directory.
Excel's entry point, tool schemas and application arguments remain unchanged.

## Live Yahoo — 2026-09-25

Both arms and the grader now read Yahoo live, as upstream does, and the
2026-09-10 capture is gone with `capture-nvidia`, `derive-nvidia` and
`nvidia-lineage`. The grader's Sheet1 snapshot is still the
fixed June 2026 one; its holder checks for Sheet2 and Sheet3 call
`yf.Ticker(...)` at grading time, through the same recording transport as
the agent's tools.
