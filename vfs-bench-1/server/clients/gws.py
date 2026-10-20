import json
import os
import urllib.error
import urllib.parse
import urllib.request

# The client side of mirage's fake Google Workspace server, which
# `bin/start.sh up` runs. Seeders and verifiers both reach
# Drive and Sheets through here rather than each writing the same twenty
# lines of `urllib` -- `nhl-b2b-analysis` and `music-analysis` carried
# byte-identical copies of `call()`, and a fixture helper that exists in
# five slightly different versions is five places for one of them to drift.
#
# Deliberately stdlib-only and deliberately thin: it speaks the same JSON
# API the real Drive v3 and Sheets v4 clients speak, so what a seeder writes
# through it is what the MCP arm's `google_sheet` server and the mirage
# arm's `gws` mount read back.

SHEET_MIME = "application/vnd.google-apps.spreadsheet"
FOLDER_MIME = "application/vnd.google-apps.folder"
# The fake's own fixture credential. It refuses a request that carries no
# token or one it did not issue, and it issues only in exchange for this.
TOKEN = "gws-integ-token"


def base() -> str:
    """Where the fake is listening.

    Returns:
        str: the base URL, without a trailing slash.
    """
    return os.environ.get("GWS_URL", "http://127.0.0.1:19999").rstrip("/")


def call(method: str, path: str, body: object | None = None) -> dict:
    """Issue one JSON request against the fake and decode the answer.

    Args:
        method (str): HTTP verb.
        path (str): path below the base URL, leading slash included.
        body (object | None): JSON request body, or None.

    Returns:
        dict: the decoded reply, or {} for an empty one.
    """
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(f"{base()}{path}",
                                     data=data,
                                     method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as raised:
        # An answered request is not a missing process, and the advice below
        # would send the reader after one that is already up. What the fake
        # said is the whole diagnosis: a kit fake answers a vendor route with
        # the tenant it could not find.
        detail = raised.read(400).decode("utf-8", "replace")
        raise SystemExit(f"mock GWS at {base()}{path} answered "
                         f"{raised.code}: {detail}") from raised
    except (urllib.error.URLError, OSError) as raised:
        # Naming the script to run beats a bare ConnectionRefusedError: the
        # fake is a long-lived process an operator starts once, so "it is
        # not running" is the likeliest cause by a wide margin.
        raise SystemExit(f"no mock GWS at {base()}{path} ({raised}); start "
                         f"it with bin/start.sh up") from raised
    return json.loads(raw) if raw else {}


def reset(**settings) -> None:
    """Empty the fake, so a seeder starts from nothing.

    Args:
        **settings: optional server settings to apply on the way, e.g.
            `epoch` to fix the mock's clock and
            `extras={"calendarTimeZone": "Asia/Hong_Kong"}` to set the
            calendar's zone. A task whose fixture is written relative
            to "today" sets these so both arms and the evaluator agree on
            what today is.
    """
    call("POST", "/reset", dict(settings))


def create_event(calendar: str, event: dict) -> dict:
    """Put one event on a calendar.

    Args:
        calendar (str): the calendar id.
        event (dict): the event resource.

    Returns:
        dict: the created event.
    """
    return call("POST", f"/calendar/v3/calendars/{quote(calendar)}/events",
                event)


def create_folder(name: str, parent: str = "root") -> str:
    """Create one Drive folder.

    Args:
        name (str): the folder name.
        parent (str): the parent folder id.

    Returns:
        str: the new folder's id.
    """
    return call("POST", "/drive/v3/files", {
        "name": name,
        "mimeType": FOLDER_MIME,
        "parents": [parent],
    })["id"]


def create_sheet(name: str, parent: str) -> str:
    """Create one spreadsheet inside a folder.

    Args:
        name (str): the spreadsheet title.
        parent (str): the folder id it lives in.

    Returns:
        str: the new spreadsheet's id.
    """
    return call("POST", "/drive/v3/files", {
        "name": name,
        "mimeType": SHEET_MIME,
        "parents": [parent],
    })["id"]


def batch_update(sheet_id: str, requests: list[dict]) -> dict:
    """Apply a batch of structural changes to a spreadsheet.

    The general form, because a seeder that only ever added a bare tab
    would be too narrow: `music-analysis` declares each tab at the source
    workbook's exact dimensions, since the fake auto-expands a grid the way
    Sheets does and every tab would otherwise report whatever the last
    write happened to reach.

    Args:
        sheet_id (str): the spreadsheet id.
        requests (list[dict]): Sheets API request objects.

    Returns:
        dict: the reply.
    """
    return call("POST", f"/v4/spreadsheets/{sheet_id}:batchUpdate",
                {"requests": requests})


def write_values(sheet_id: str, span: str, rows: list) -> None:
    """Write a block of cells.

    Args:
        sheet_id (str): the spreadsheet id.
        span (str): an A1 range, e.g. `Sheet1!A1`.
        rows (list): rows of cell values.
    """
    call("PUT", f"/v4/spreadsheets/{sheet_id}/values/{quote(span)}",
         {"values": rows})


def read_values(sheet_id: str, span: str) -> list:
    """Read a block of cells back.

    Args:
        sheet_id (str): the spreadsheet id.
        span (str): an A1 range.

    Returns:
        list: the rows, empty if the range holds nothing.
    """
    return call("GET",
                f"/v4/spreadsheets/{sheet_id}/values/{quote(span)}").get(
                    "values", [])


def sheets(sheet_id: str) -> list[dict]:
    """Every sheet record in one spreadsheet, properties included.

    Strict where `tabs` is forgiving: the seeders that read this go on to
    index `properties`, so a spreadsheet the fake reports without a `sheets`
    key is a broken fixture and should say so here rather than seed an empty
    workbook and fail a grade later.

    Args:
        sheet_id (str): the spreadsheet id.

    Returns:
        list[dict]: the sheet records, in the order the fake reports them.
    """
    return call("GET", f"/v4/spreadsheets/{sheet_id}")["sheets"]


def grid(sheet_id: str) -> dict:
    """One spreadsheet with its cell data and formatting.

    Args:
        sheet_id (str): the spreadsheet id.

    Returns:
        dict: the spreadsheet, `sheets` carrying each tab's grid data.
    """
    return call("GET", f"/v4/spreadsheets/{sheet_id}?includeGridData=true")


def tabs(sheet_id: str) -> list[str]:
    """Every tab title in one spreadsheet.

    Args:
        sheet_id (str): the spreadsheet id.

    Returns:
        list[str]: the titles, in the order the fake reports them.
    """
    meta = call("GET", f"/v4/spreadsheets/{sheet_id}")
    return [s["properties"]["title"] for s in meta.get("sheets", [])]


def find(name: str, mime: str | None = None) -> list[dict]:
    """Drive files matching one exact name.

    Args:
        name (str): the file name to match.
        mime (str | None): keep only this mime type, if given.

    Returns:
        list[dict]: the matching file records.
    """
    files = call("GET", f"/drive/v3/files?q={quote(f'name = {name!r}')}").get(
        "files", [])
    return [f for f in files if mime is None or f.get("mimeType") == mime]


def quote(value: str) -> str:
    """Percent-encode one path or query segment.

    `safe=""` rather than the default: a tab title carries whatever the
    source workbook called it, and `music-analysis` has one named
    "Top 1,000" -- a slash in a title would otherwise split the path.

    Args:
        value (str): the raw value.

    Returns:
        str: the encoded value.
    """
    return urllib.parse.quote(value, safe="")
