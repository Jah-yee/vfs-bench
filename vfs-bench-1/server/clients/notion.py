import json
import os
import urllib.error
import urllib.request

# The client side of mirage's fake Notion REST API, which
# `bin/start.sh up` runs. Same shape and same reason as `gws.py`: the
# seeders that reach Notion were each carrying their own `urllib` helper.


def base() -> str:
    """Where the fake is listening.

    Returns:
        str: the base URL, without a trailing slash.
    """
    return os.environ.get("NOTION_URL", "http://127.0.0.1:5091").rstrip("/")


def call(method: str,
         path: str,
         body: object | None = None,
         token: str = "fake") -> dict:
    """Issue one JSON request against the fake and decode the answer.

    Args:
        method (str): HTTP verb.
        path (str): path below the base URL, leading slash included.
        body (object | None): JSON request body, or None.
        token (str): the bearer token, which *is* the workspace on this
            fake. `reset` addresses a workspace by name in its body, so the
            default suffices there; a read has to carry the task's own
            token or it looks at the wrong workspace.

    Returns:
        dict: the decoded reply, or {} for an empty one.

    Raises:
        SystemExit: the server is not running.
    """
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(f"{base()}{path}",
                                     data=data,
                                     method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except (urllib.error.URLError, OSError) as raised:
        raise SystemExit(f"no mock Notion at {base()}{path} ({raised}); "
                         f"start it with bin/start.sh up") from raised
    return json.loads(raw) if raw else {}


def reset(workspace: str, fixture: str) -> dict:
    """Re-seed one workspace from one of the fake's named fixtures.

    A bearer token *is* a tenant on mirage's fake, and a tenant is a column
    inside the run rather than a database of its own, so a reset is a delete
    restricted to the names given: resetting one leaves every other notion
    task's workspace on the same server alone, which is what lets five tasks
    share one process without a reset order.

    Args:
        workspace (str): the workspace token, which names the tenant.
        fixture (str): the fixture NAME, not a path. The kit resolves it
            under the fake's own fixtures/notion/ and re-checks the result
            is inside that directory, so neither `..` nor an absolute path
            can escape; docker/compose.yml bind-mounts this repo's rows onto
            the names it answers to.

    Returns:
        dict: the reply.

    Raises:
        SystemExit: the fake refused the reset.
    """
    reply = call("POST", "/reset", {
        "tenants": [workspace],
        "fixture": fixture,
    })
    if not reply.get("ok"):
        raise SystemExit(f"notion reset refused: {reply}")
    return reply
