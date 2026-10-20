import json
import os
import urllib.error
import urllib.request

# The client side of server/api/app.py's logging routes, stdlib only: it is
# imported by `sitecustomize.py` inside the google-cloud server's and the
# evaluators' interpreters, none of which should need anything installed to
# append a log line. The variable carries the
# whole per-task base, e.g. http://127.0.0.1:9110/api/ab-testing/logging,
# composed by whoever knows the task name.
ENV = "CLOUD_LOGGING_API"

# Cloud Logging's own severity order; mirrors the store's table, which is
# a fixed public enum, not something this repo invented.
SEVERITIES = {
    "DEFAULT": 0,
    "DEBUG": 100,
    "INFO": 200,
    "NOTICE": 300,
    "WARNING": 400,
    "ERROR": 500,
    "CRITICAL": 600,
    "ALERT": 700,
    "EMERGENCY": 800,
}


class FilterError(ValueError):
    """A filter the store refused; re-raised from the server's 400."""


def call(path: str, payload: dict | None = None, method: str = "POST"):
    """One request against the task's logging endpoint.

    Args:
        path (str): route below the base, e.g. `/entries:write`.
        payload (dict | None): JSON body, if any.
        method (str): HTTP method.

    Returns:
        the decoded JSON answer.

    Raises:
        FilterError: the server said 400, which is the filter parser
            refusing an operator it does not implement.
        RuntimeError: the endpoint is unset or unreachable -- a fake that
            fails loudly costs turns; one that succeeds wrongly costs the
            grade, so nothing here degrades to a no-op.
    """
    base = os.environ.get(ENV)
    if not base:
        raise RuntimeError(f"{ENV} is not set; start the fixture API with "
                           f"bin/start.sh up and point this at "
                           f"http://127.0.0.1:9110/api/<task>/logging")
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as failure:
        body = failure.read().decode(errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except ValueError:
            detail = body
        if failure.code == 400:
            raise FilterError(detail) from failure
        raise RuntimeError(f"logging api: HTTP {failure.code}: "
                           f"{detail}") from failure
    except urllib.error.URLError as failure:
        raise RuntimeError(f"logging api unreachable at {base}: "
                           f"{failure.reason}; start it with "
                           f"bin/start.sh up") from failure


def write(entries, logger_name=None, resource=None, labels=None) -> None:
    call(
        "/entries:write", {
            "entries": list(entries),
            "logger_name": logger_name,
            "resource": resource,
            "labels": labels,
        })


def select(filter_, order_by=None, max_results=None) -> list[dict]:
    return call("/entries:select", {
        "filter": filter_,
        "order_by": order_by,
        "max_results": max_results,
    })["entries"]


def delete_log(log_name: str) -> int:
    return call("/logs:delete", {"log_name": log_name})["deleted"]


def clear_entries() -> None:
    call("/entries:clear")


def buckets() -> dict[str, dict]:
    return call("/buckets", method="GET")["buckets"]


def put_bucket(name: str, fields: dict) -> None:
    call("/buckets:put", {"name": name, "fields": fields})


def drop_bucket(name: str) -> bool:
    return call("/buckets:drop", {"name": name})["dropped"]
