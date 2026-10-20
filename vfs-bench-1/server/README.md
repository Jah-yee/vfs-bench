# server/

Everything that serves a tool surface, one directory per role:

    server/
    ├── api/                  the fixture API -- one process, bin/start.sh up
    │   ├── app.py            FastAPI app: /api/<task>/<service>/...
    │   └── logging_store.py  the Cloud Logging engine and filter parser
    ├── mcp/                  the --tools mcp arm
    │   └── mcp_servers.py    one builder per upstream MCP server
    └── bq/                   sidecars for the BigQuery emulator
        ├── proxy.py          corrects the emulator's three known defects
        └── token_stub.py     OAuth endpoint for its signed credentials

None of these files is optional machinery; each exists because a specific
fake cannot be reached any other way:

| file | why it has to exist |
|---|---|
| `bq/proxy.py` | `goccy/bigquery-emulator` mislabels user SQL errors as internal, drops CSV headers from extracts, and omits dataset-level `INFORMATION_SCHEMA.TABLES` and `COLUMNS` views. The proxy corrects those differences from the emulator's live REST catalog. |
| `bq/token_stub.py` | `BIGQUERY_EMULATOR_HOST` rewrites the endpoint but does **not** waive credential signing, so the service-account key needs a token endpoint to sign against |
| `redirect/*/[*.mjs]` | `googleapis` hardcodes its host and the fetch server calls the platform `fetch`; neither honours any environment variable, so the redirect has to be loaded before the server's module graph — which is why those two live in `redirect/` rather than here. Slated for removal once those two servers route through the API |
| `api/logging_store.py` | Cloud Logging has no public emulator at all — this is the engine, and the filter parser refuses what it does not implement rather than matching everything |

## The API

    bin/start.sh up             # http://127.0.0.1:9110, long-lived

`api/`, `bq/proxy.py` and `bq/token_stub.py` all run in the stack image
(`docker/`), which serves six roles out of one build by argument. They still
run on the host unchanged — every bind address and upstream in them
defaults to loopback and is only overridden inside a container, where
binding the loopback would publish a port that accepts a connection and then
answers nothing.

`/stack/healthz` on this port reports every fake in the stack in one
request, and carries `bq_launch_time` — the value a generated BigQuery
fixture named its answer table after, which the evaluator has to be handed
and which used to cross that boundary as a scraped log line.

Routes are `/api/<task>/<service>/...` and the task segment is the
namespace: each task's state lives in its own directory
(`state/cloud_logging/<task>/`), so nothing an arm writes is visible to
another task. Consumers are all thin clients on one implementation:

| consumer | through |
|---|---|
| mirage arm's `google-cloud` CLI | the MCP arm's own server, over that same redirect |
| MCP arm's `google-cloud` server | `redirect/cloud_logging/`, whose transport is that same client |
| upstream's preprocess and evaluators | the same redirect, from `task/toolathlon/script/grade_task.py` |
| `server/seed/seed_logging.py` | the client, directly |

The `PYTHONPATH` redirect survives the move for one reason: the Google
client libraries honour no endpoint override for logging, so replacing the
transport at interpreter start-up is still the only door into the MCP
server and the evaluators. What changed is what the replacement *is* — a
stdlib HTTP client instead of a second copy of the store — so parsing,
stamping and ordering happen in exactly one process. Only processes that
import `google.cloud.logging` need the redirect; the mirage CLI imports the
client itself.

What the loop has to hold for is every call the three graded tasks make,
in both directions, refusals included: `ab-testing`'s whole grade is that a
log comes back *empty*, so a filter that quietly matched everything would
let both arms pass. `task/toolathlon/<task>/tests/parity.json` is where that is
written down as cases `tests/parity.py` can run.

**Next behind the API:** snowflake. It talks to the fixture Postgres
directly today (`clients/snowflake.py`); the redirect stays as the door into
upstream's processes, the module becomes a client on `/api/<task>/snowflake`,
and the mirage CLI (`sql`) calls the same route. Postgres namespacing per
task (one schema or database per task) rides in with that change.

## The MCP arm

`mcp/mcp_servers.py` launches *upstream's own servers* — vendored and
pinned, over stdio, exactly as Toolathlon configures them. That is
deliberate and load-bearing: the tool list and schemas each task's agent
sees are half of what this benchmark measures, and they must map to the
original Toolathlon task — per task, since two tasks can hold different
slices of the same service (`flagged-transactions` gets BigQuery only;
`machine-operating` gets storage too; the split comes from each task's
`token_key_session.py` and `task_config.json`, never restated here).

So "handled by the MCP server" means: the servers stay upstream's, and
*aiming them at fixtures* is this directory's job.

## The TypeScript mocks

Drive/Sheets (`integ/server/gws/`) and Notion (`integ/server/notion/`) are
mirage's own integ servers, copied into the stack image from the pinned
submodule along with `integ/server/kit/`, which both now import
(and still runnable on the host by `bin/start.sh up` and
`bin/start.sh up`). Between them they need four npm packages, so the
image installs those four rather than the 1.7GB mirage workspace they
normally resolve through. They stay separate processes rather than moving
into
`api/`: they already speak the real wire protocols, both arms already share
them, and a second implementation of Drive v3 + the Notion REST API is
exactly the fake-that-succeeds-wrongly risk this repo avoids. The
integration point is the environment (`GWS_URL`, `NOTION_URL`) and, later,
per-task namespacing inside them (`INTEG_DB_URL` is already one SQLite file
per checkout for Notion). GreenMail, fake-gcs-server and the BigQuery
emulator are third-party images behind their own `bin/start_*.sh` for the
same reason.
