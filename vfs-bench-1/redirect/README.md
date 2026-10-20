# redirect/

Nothing here implements a fake. Everything here exists because a process we
cannot edit imports a name we do not own.

The fakes themselves are in [`server/clients/`](../server/clients/README.md) — ordinary modules with
ordinary names. This directory is only the spelling upstream's client asks
for, and it is kept separate so that the mirage arm, which has no such
client, never has to reach through a shadow to get at an implementation.

| entry | claims the name | for |
|---|---|---|
| `snowflake/` | `snowflake.connector`, `snowflake.snowpark` | the MCP server's `db_client.py` and three evaluators → `server/clients/snowflake.py` |
| `yahoo_capture/` | `yfinance.Ticker` | the Yahoo MCP server and upstream's yahoo evaluators → the live SDK, through the recording transport in `server/seed/public_services.py` |
| `excel/` | `logging.FileHandler` for `excel-mcp.log` | original Excel MCP log → the run's writable scratch directory |
| `cloud_logging/` | the `google.cloud.logging` transport | the `google-cloud` server and its evaluators → `server/clients/cloud_logging.py` |
| `bigquery/` | `bigquery.Client.load_table_from_json` | upstream's preprocess, which the emulator has no load-job API for |
| `gws_sheets/` | `google.oauth2`'s credentials, plus a fake token | upstream's `google_sheet` server |
| `gws_calendar/` | `googleapis`' rootUrl, plus fake OAuth files | the calendar server, via a `node --import` hook |
| `fetch/` | `globalThis.fetch` | the fetch server, via the same mechanism |
| `eval_shim/` | `api.github.com`, `api.notion.com`, Google hosts | upstream's evaluators, which hardcode them |
| `hub/` | `requests` calls to `huggingface.co` | the MCP arm's model Python on a task with the Hub → the Hub fake, through `eval_shim/hf_host.py` |

## The rule

A divergence may change **where bytes come from**. It may never change
**what the model is sent**. Everything here is the first kind: the server
still lists the same tool names with the same schemas, and would if launched
upstream's way. Nothing here edits a tool, a description or a schema.

## Two shapes

Most entries are a **`PYTHONPATH` entry** — a directory whose contents
shadow an installed package, or a `sitecustomize.py` that Python runs at
interpreter start-up. Python imports the first match on the path, so putting
one of these first is the whole mechanism.

Two are a **`node --import` preload**, because `googleapis` hardcodes its
host and the fetch server calls the platform `fetch`; neither honours an
environment variable, so the redirect has to be loaded before the server's
module graph is built.

Each directory is one `PYTHONPATH` entry, and each one puts the repository
root on `sys.path` itself rather than asking its caller for a second entry.
Both `sitecustomize.py` names cannot be on the path at once — no process
needs two, and every launcher passes exactly one.

## Where each one is installed

`server/mcp/mcp_servers.py` for the MCP arm, `task/toolathlon/script/grade_task.py` for the
evaluators, `bin/start.sh` and `uv run python server/fakes/gcp.py` for BigQuery,
`setup/toolathlon/setup_toolathlon.py` for the two paths that upstream's own
yaml has to carry. Those are the only places any of it is spelled.
