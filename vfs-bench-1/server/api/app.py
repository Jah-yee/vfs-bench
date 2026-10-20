import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import logging_store as store
from fastapi import FastAPI, HTTPException

# The fixture API: every service this repo fakes that has no wire protocol
# of its own, served over HTTP so each consumer -- the mirage CLIs, the MCP
# arm's shims, the seeders, the evaluators -- is a thin client on one
# implementation. Routes are /api/<task>/<service>/..., and the task
# segment is the namespace: state lives per task, so nothing an arm writes
# is visible to another task's run. Cloud Logging is the first service
# here; yfinance and snowflake are next (see server/README.md).
#
#     bin/start.sh up           # serves http://127.0.0.1:9110

REPO_ROOT = Path(__file__).resolve().parents[2]
LOGGING_ROOT = Path(
    os.environ.get("CLOUD_LOGGING_ROOT",
                   REPO_ROOT / "state" / "cloud_logging"))

FIXTURE_DIR = Path(os.environ.get("FIXTURE_DIR", "/fixtures"))


def probes() -> dict[str, tuple[str, str | None]]:
    """Every fake in the stack, and one request each that proves it useful.

    Answering, not merely listening: the BigQuery pair are asked for the
    running task's own datasets rather than for a generic endpoint, so a
    200 here means the fixture loaded. The project is whatever
    bin/start.sh last brought the profile up for.

    Siblings are reached by compose service name, so this reports what
    another container can see -- which is the question the MCP servers will
    ask once they move in beside these.

    Returns:
        dict[str, tuple[str, str | None]]: service -> (url, auth header).
    """
    project = "probe"
    record = FIXTURE_DIR / "fixture.json"
    if record.is_file():
        project = (json.loads(record.read_text()).get("bigquery")
                   or {}).get("project") or project
    datasets = f"/bigquery/v2/projects/{project}/datasets"
    # The emulator is the one sibling whose in-network port moves with its
    # published one: it writes its own listen address into upload URLs.
    bigquery = os.environ.get("BQ_PORT", "9050")
    return {
        "logging": ("http://127.0.0.1:9110/healthz", None),
        "gws": ("http://gws:19999/drive/v3/files", None),
        "notion": ("http://notion:5091/v1/users/me", "Bearer probe"),
        "github": ("http://github:19801/user", "Bearer probe"),
        "mail": ("http://mail:8080/api/service/readiness", None),
        "bigquery": (f"http://bigquery:{bigquery}{datasets}", None),
        "gcs": ("http://gcs:4443/storage/v1/b?project=probe", None),
        "bqproxy": (f"http://bqproxy:9051{datasets}", None),
        "tokenstub": ("http://tokenstub:9061/token", None),
    }


app = FastAPI(title="vfs-bench fixture API")


def probe(target: tuple[str, str | None]) -> dict:
    """Ask one service whether it is answering.

    Args:
        target (tuple[str, str | None]): its URL and Authorization header.

    Returns:
        dict: `up`, and `status` or `error`.
    """
    url, auth = target
    request = urllib.request.Request(
        url, headers={"Authorization": auth} if auth else {})
    try:
        with urllib.request.urlopen(request, timeout=3) as reply:
            return {"up": True, "status": reply.status}
    except urllib.error.HTTPError as failure:
        # An answered 4xx still proves the service is up; only a refused or
        # timed-out connection means it is not. The token stub answers 405
        # to a GET, the emulator 404 to an unknown path -- both are alive.
        return {"up": True, "status": failure.code}
    except Exception as failure:
        return {"up": False, "error": f"{type(failure).__name__}: {failure}"}


def scoped(task: str) -> None:
    """Point the store at this task's own directory for this request."""
    if not task or "/" in task or task.startswith("."):
        raise HTTPException(status_code=400, detail=f"bad task {task!r}")
    store.ROOT_OVERRIDE.set(str(LOGGING_ROOT / task))


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "services": ["logging"]}


@app.get("/stack/healthz")
def stack_healthz() -> dict:
    """Whether the whole fixture stack is ready, in one request.

    `docker compose ps` answers whether the containers are running, which
    is a different question: a service can be up and still be answering
    401s at a path the arms depend on. This asks each one something it has
    to serve correctly to be useful.

    BigQuery, Cloud Storage and their two helpers are optional -- they come
    up per task under the `gcp` profile -- so they are reported but do not
    decide `ok`.

    Returns:
        dict: `ok`, per-service results, and the frozen BigQuery launch
            time when a gcp profile is running.
    """
    targets = probes()
    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        results = dict(
            zip(targets, pool.map(probe, targets.values()), strict=True))
    optional = {"bigquery", "gcs", "bqproxy", "tokenstub"}
    required = {k: v for k, v in results.items() if k not in optional}

    # The evaluator has to be handed the same launch time the fixture was
    # generated for, or it looks for a table nobody was asked to make.
    # bin/start.sh freezes it into the shared volume; reporting it here is
    # what lets a caller read it back over the wire instead of scraping a
    # log line.
    launch = None
    record = FIXTURE_DIR / "fixture.json"
    if record.is_file():
        launch = json.loads(record.read_text()).get("seeded_at")

    return {
        "ok": all(r["up"] for r in required.values()),
        "services": results,
        "bq_launch_time": launch,
    }


@app.post("/api/{task}/logging/entries:write")
def entries_write(task: str, body: dict) -> dict:
    scoped(task)
    store.write(
        list(body.get("entries") or []),
        body.get("logger_name"),
        body.get("resource"),
        body.get("labels"),
    )
    return {"written": len(body.get("entries") or [])}


@app.post("/api/{task}/logging/entries:select")
def entries_select(task: str, body: dict) -> dict:
    scoped(task)
    try:
        rows = store.select(
            body.get("filter"),
            body.get("order_by"),
            body.get("max_results"),
        )
    except store.FilterError as failure:
        # 400 carries the parser's own message; the client re-raises it as
        # a FilterError so a CLI's usage error reads the same as before.
        raise HTTPException(status_code=400, detail=str(failure))
    return {"entries": rows}


@app.post("/api/{task}/logging/entries:clear")
def entries_clear(task: str) -> dict:
    scoped(task)
    store.clear_entries()
    return {"cleared": True}


@app.post("/api/{task}/logging/logs:delete")
def logs_delete(task: str, body: dict) -> dict:
    scoped(task)
    return {"deleted": store.delete_log(body["log_name"])}


@app.get("/api/{task}/logging/buckets")
def buckets_list(task: str) -> dict:
    scoped(task)
    return {"buckets": store.buckets()}


@app.post("/api/{task}/logging/buckets:put")
def buckets_put(task: str, body: dict) -> dict:
    scoped(task)
    store.put_bucket(body["name"], dict(body.get("fields") or {}))
    return {"name": body["name"]}


@app.post("/api/{task}/logging/buckets:drop")
def buckets_drop(task: str, body: dict) -> dict:
    scoped(task)
    return {"dropped": store.drop_bucket(body["name"])}
