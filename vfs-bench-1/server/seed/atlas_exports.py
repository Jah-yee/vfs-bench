import csv
import datetime
import hashlib
import io
import json
import os
import re
import selectors
import subprocess
import sys
import urllib.request
import uuid
import zipfile
from contextlib import ExitStack
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "task"))
sys.path.insert(0, str(REPO / "agent"))

# The exports Atlas ships for the services its tasks read online
# (`data_exports/README.md`): a user imports each into a live account, and
# the recorded trajectories are what that account answered.
EXPORTS = "data_exports"
NOTION_EXPORT = "mcp-atlas-notion-data.zip"

# Atlas's Slack workspace, as mirage builds it out of the same export
# (`scripts/gen_slack_atlas.py`) and replays Atlas's recorded Slack calls
# against (`integ/slack_atlas.ts`): every message with its subtype, the two
# files, and the messages moved back the 161 days the export moved them
# forward, to the dates the recordings read. Read at mirage's pin, as the
# fake it seeds is.
SLACK_CORPUS = "integ/truth/slack_atlas.json"

# What the recordings pin that an export does not: every database's schema --
# property ids, option ids and colours -- the members, and the ids of the
# rows any recorded reply carried. mirage keeps them, rebuilt byte for byte
# out of the same parquet (`scripts/gen_notion_atlas.py`), for its own replay
# of Atlas's Notion calls; read at mirage's pin, as the fake it seeds is.
NOTION_CORPUS = "integ/truth/notion_atlas.json"

# Atlas's Airtable base, which it ships as a share link to copy rather than
# as an export: mirage captures it from that link (`scripts/
# gen_airtable_atlas.py`) and replays Atlas's recorded Airtable calls against
# it (`integ/airtable_atlas.ts`). Every record, in the public API's shape,
# with the account the fake answers for. Read at mirage's pin, as the fake it
# seeds is.
AIRTABLE_CORPUS = "integ/truth/airtable_atlas.json"

# Atlas's calendar, as Google exports one: the `.ics` a user imports into a
# fresh account.
CALENDAR_EXPORT = "calendar_mcp_eval_export.zip"

# mirage's own base world for its Google Workspace fake -- the four system
# labels and the primary calendar -- which Atlas's calendar is put into. Read
# at mirage's pin, as the fake it seeds is.
GWS_BASE = "integ/fixtures/gws/v1.json"

# The zone the recordings read the calendar in. The export names
# America/Los_Angeles (`X-WR-TIMEZONE`), but all 22 recorded `list_events`
# replies render every event in America/New_York, which is the zone of the
# account Atlas imported it into.
CALENDAR_ZONE = "America/New_York"

# Google expands a series with no end afresh on every read; the fake stores
# the instances themselves, so an endless series is expanded up to here --
# past any window a run reads, the rolling window the mirage arm's calendar
# mount lists around today included.
SERIES_HORIZON = datetime.datetime(2030, 1, 1, tzinfo=datetime.UTC)

# The zone an event names of its own, which the export drops: it writes every
# time in UTC. One event names one, the one created after the import
# (2025-08-01), which every recording that reads it renders in UTC.
EVENT_ZONES = {"nhs0limtb5tujvl12h16pg6duo": "UTC"}

# Atlas's MongoDB, as `mongodump` wrote it: the `video_game_store` database
# a user restores into a cluster of their own.
MONGO_EXPORT = "mongo_dump_video_game_store-UNZIP-FIRST.zip"
MONGO_DUMP = "mongo_dump_video_game_store"

# The server it is restored into, with the `mongorestore` its image carries:
# MongoDB 7.0, where the free Atlas cluster `data_exports/README.md` restores
# the dump into runs 8.0 -- every 8.0 build refuses to start on a Linux kernel
# from 6.19 up to 7.0.14 (SERVER-121912), which Docker Desktop's 7.0.12 is.
MONGO_IMAGE = ("mongo@sha256:9854f7139445d766a9523571d6f047530c45547460ff"
               "cf8259eb2bf4264632ca")

# The fixture name, which is also the tenant, in both fakes: each seeds the
# tenant a token names from the fixture of that name.
TENANT = "atlas"

# Where a fake answers otherwise. mirage's gws fake reads no tenant from a
# Google credential and answers every one as its default, so that is the
# tenant the calendar is seeded into; mirage's github fake reads none from
# its token either.
TENANTS = {"calendar": "default", "github": "default"}

URL_BASE = "https://www.notion.so/"
ANNOTATIONS = {
    "bold": False,
    "italic": False,
    "strikethrough": False,
    "underline": False,
    "code": False,
    "color": "default",
}


def pinned(submodule: str) -> str:
    """The commit this checkout's gitlink records for a submodule.

    Args:
        submodule (str): the path under the repository root.

    Returns:
        str: the full sha.
    """
    return subprocess.run(
        ["git", "-C",
         str(REPO), "rev-parse", f"HEAD:./{submodule}"],
        capture_output=True,
        text=True,
        check=True).stdout.strip()


def shown(submodule: str, path: str) -> bytes:
    """One file as a submodule's pinned commit has it.

    Read out of git rather than the working tree, for the reason
    `mcp_servers.upstream_config` gives: a checkout can be anywhere, and the
    pin is what the fixture must trace to.

    Args:
        submodule (str): the path under the repository root.
        path (str): the path inside the submodule.

    Returns:
        bytes: the file's contents.
    """
    return subprocess.run([
        "git", "-C",
        str(REPO / submodule), "show", f"{pinned(submodule)}:{path}"
    ],
                          capture_output=True,
                          check=True).stdout


def rich(text: str) -> list:
    """A plain rich-text run, as live Notion renders an imported cell.

    Args:
        text (str): the cell.

    Returns:
        list: no runs for an empty cell, one otherwise.
    """
    if text == "":
        return []
    return [{
        "type": "text",
        "text": {
            "content": text,
            "link": None
        },
        "annotations": dict(ANNOTATIONS),
        "plain_text": text,
        "href": None,
    }]


def cell(column: dict, text: str):
    """One CSV cell as the property value Notion's importer made of it.

    Every rule here is read off the recordings, and `notion_workspace` refuses
    a fixture in which any recorded row fails to come back from its CSV row.

    Args:
        column (dict): the database's property object.
        text (str): the CSV cell.

    Returns:
        The value under the property's type key.

    Raises:
        ValueError: a property type the export does not use.
    """
    kind = column["type"]
    if kind in ("title", "rich_text"):
        return rich(text)
    if text == "":
        return None
    if kind == "number":
        value = float(text)
        return int(value) if value.is_integer() and "." not in text else value
    if kind == "select":
        option = next(o for o in column["select"]["options"]
                      if o["name"] == text)
        return {
            "id": option["id"],
            "name": option["name"],
            "color": option["color"]
        }
    if kind == "checkbox":
        return {"Yes": True, "No": False}[text]
    if kind == "date":
        day = datetime.datetime.strptime(text, "%B %d, %Y").date()
        return {"start": day.isoformat(), "end": None, "time_zone": None}
    raise ValueError(f"no rule for a {kind} property")


def bare(column: dict, value):
    """A property value as mirage's corpus stores it, for matching.

    Args:
        column (dict): the database's property object.
        value: the value under the property's type key.

    Returns:
        The bare cell, None where the corpus stores none.
    """
    kind = column["type"]
    if kind in ("title", "rich_text"):
        return "".join(run["plain_text"] for run in value) or None
    if kind == "select":
        return None if value is None else value["name"]
    if kind == "date":
        return None if value is None else value["start"]
    return value


def page_url(title: str, page: str) -> str:
    """The url Notion gives a page, from its title and id.

    Args:
        title (str): the page's title.
        page (str): its id.

    Returns:
        str: the url.
    """
    slug = re.sub(r"[^A-Za-z0-9_]+", "-", title).strip("-")
    return f"{URL_BASE}{slug + '-' if slug else ''}{page.replace('-', '')}"


def notion_workspace() -> dict:
    """Atlas's Notion workspace, every row of it, as the fake's fixture.

    The rows are the export's six CSVs, all 29,388 of them -- the
    recordings only carry the 1,599 some agent happened to read, and a task
    that counts rows needs the rest. Each is rendered with its database's
    recorded schema; a row a recording carried keeps that recording's id
    and url, and every recorded row must come back from some CSV row or
    nothing is written.

    Stored in reverse CSV order, which is the order recorded unsorted
    queries returned. The export's one page, "Real Estate Strategy",
    is not in it: five recorded searches for "real estate" returned the
    database alone, so the integration Atlas recorded through could not see
    the page, and neither can this one.

    Returns:
        dict: the fixture, in the shape mirage's notion fake reads.

    Raises:
        SystemExit: the export and the recordings disagree.
    """
    corpus = json.loads(shown("submodule/mirage", NOTION_CORPUS))
    with zipfile.ZipFile(
            io.BytesIO(
                shown("submodule/mcp-atlas",
                      f"{EXPORTS}/{NOTION_EXPORT}"))) as archive:
        exported = {
            Path(name).stem: archive.read(name).decode("utf-8-sig")
            for name in archive.namelist()
            if name.endswith(".csv") and not name.startswith("__MACOSX")
        }
    bot = next(u for u in corpus["users"] if "bot" in u)
    first = corpus["tables"][0]
    databases, pages = [], []
    for position, table in enumerate(corpus["tables"]):
        db = table["database"]
        title = "".join(part["plain_text"] for part in db["title"])
        schema = db["properties"]
        rows = list(csv.DictReader(io.StringIO(exported[title])))
        if set(rows[0]) != set(schema):
            raise SystemExit(f"notion: {title}'s CSV columns are not its "
                             f"recorded properties")
        rendered = [{
            name: {
                "id": schema[name]["id"],
                "type": schema[name]["type"],
                schema[name]["type"]: cell(schema[name], row[name]),
            }
            for name in table["columns"]
        } for row in rows]
        cells = [[
            bare(schema[name], props[name][schema[name]["type"]])
            for name in table["columns"]
        ] for props in rendered]
        recorded = {}
        for raw in table["rows"]:
            page, url, *values = raw
            # A recording made with `filter_properties` carries some columns
            # and not others, and the corpus stores the rest as None: a
            # wildcard, not an empty cell. Such a row may fit several CSV
            # rows, and then which one it was is not recorded -- the row
            # keeps an id of its own like any unrecorded row.
            known = [(i, v) for i, v in enumerate(values) if v is not None]
            found = [
                index for index, row in enumerate(cells)
                if all(row[i] == v for i, v in known)
            ]
            if not found:
                raise SystemExit(f"notion: {title} row {page} is in no CSV "
                                 f"row")
            if len(found) == 1:
                if found[0] in recorded:
                    raise SystemExit(f"notion: {title} CSV row {found[0]} "
                                     f"is two recorded rows")
                recorded[found[0]] = (page, url)
        databases.append({
            "id": db["id"],
            "parentType": "workspace",
            "parentId": None,
            "titleText": title,
            "titleJson": db["title"],
            "descriptionJson": db.get("description") or [],
            "propertiesJson": schema,
            "isInline": db.get("is_inline") is True,
            "inTrash": False,
            "createdTime": db["created_time"],
            "lastEditedTime": db["last_edited_time"],
            "createdBy": db["created_by"]["id"],
            "lastEditedBy": db["last_edited_by"]["id"],
            "url": db["url"],
            "position": position,
        })
        title_column = next(n for n in table["columns"]
                            if schema[n]["type"] == "title")
        # Reverse CSV order is live Notion's order to within a few adjacent
        # swaps, and mirage stores the recorded rows in the one order every
        # recorded reply agrees with, swaps included. So each recorded row's
        # slot in the reverse order is refilled in the corpus's order: the
        # recorded rows are where the recordings saw them, and every other
        # row keeps its place.
        order = list(reversed(range(len(rendered))))
        page_index = {page: index for index, (page, _) in recorded.items()}
        seen = [
            page_index[raw[0]] for raw in table["rows"] if raw[0] in page_index
        ]
        slots = iter(seen)
        order = [next(slots) if i in recorded else i for i in order]
        for index in order:
            props = rendered[index]
            name = "".join(run["plain_text"]
                           for run in props[title_column]["title"])
            page, url = recorded.get(index, (None, None))
            page = page or str(uuid.uuid5(uuid.UUID(db["id"]), f"row-{index}"))
            pages.append({
                "id": page,
                "parentType": "database_id",
                "parentId": db["id"],
                "titleText": name,
                "propertiesJson": props,
                "iconJson": None,
                "coverJson": None,
                "inTrash": False,
                "createdTime": table["created_time"],
                "lastEditedTime": table["last_edited_time"],
                "createdBy": table["author"],
                "lastEditedBy": table["author"],
                "url": url or page_url(name, page),
                "position": len(pages),
            })
    return {
        "meta": {
            "workspaceName":
            bot["bot"]["workspace_name"],
            # Not in any recording; mirage's replay uses the same one.
            "workspaceId":
            "a7a50000-0000-4000-8000-000000000000",
            "botId":
            bot["id"],
            "botName":
            bot["name"],
            "maxUploadSize":
            bot["bot"]["workspace_limits"]["max_file_upload_size_in_bytes"],
            "urlBase":
            URL_BASE,
            "createdTime":
            first["created_time"],
            "lastEditedTime":
            first["last_edited_time"],
            "createdBy":
            first["author"],
            "lastEditedBy":
            first["author"],
        },
        "databases":
        databases,
        "pages":
        pages,
        "users": [{
            "id": u["id"],
            "name": u["name"],
            "avatarUrl": u.get("avatar_url"),
            "type": u["type"],
            "detailJson": u.get(u["type"]) or {},
        } for u in corpus["users"] if u["id"] != bot["id"]],
    }


def slack_workspace() -> dict:
    """Atlas's Slack workspace as the fake's fixture.

    Mirage's own, out of `SLACK_CORPUS`, rather than rebuilt here: it is the
    workspace mirage's CI replays the recordings against, so a reply this
    fake gives is one that replay has held to live Slack's.

    Returns:
        dict: the fixture, in the shape mirage's slack fake reads.
    """
    return json.loads(shown("submodule/mirage", SLACK_CORPUS))["workspace"]


def airtable_workspace() -> dict:
    """Atlas's Airtable base as the fake's fixture.

    Mirage's own, out of `AIRTABLE_CORPUS`, for the reason `slack_workspace`
    gives.

    Returns:
        dict: the fixture, in the shape mirage's airtable fake reads.
    """
    return json.loads(shown("submodule/mirage", AIRTABLE_CORPUS))["workspace"]


def github_workspace() -> dict:
    """GitHub as the fake's fixture: nothing at all.

    The fake serves only tasks whose rows ask about nothing on GitHub;
    every other reads live GitHub (`GITHUB_LIVE` in
    `task/mcpatlas/__init__.py`). So a search is answered as GitHub
    answers one for what it does not hold, and it holds no repository a
    token of ours could reach.

    Returns:
        dict: the fixture, in the shape mirage's github fake reads.
    """
    return {}


def airtable_token() -> str:
    """The token the Airtable fixture's account answers to.

    Returns:
        str: the token, which both arms send.
    """
    return airtable_workspace()["tokens"][0]["token"]


def ics_events(text: str) -> list[dict]:
    """Every VEVENT of an `.ics`, as its properties.

    Args:
        text (str): the calendar.

    Returns:
        list[dict]: one dict per event, property name to `(params, value)`;
        EXDATE, which repeats, to a list of them.
    """
    events, current = [], None
    for line in re.sub(r"\r?\n[ \t]", "", text).splitlines():
        if line == "BEGIN:VEVENT":
            current = {"EXDATE": []}
        elif line == "END:VEVENT":
            events.append(current)
            current = None
        elif current is not None:
            head, value = line.split(":", 1)
            name, *params = head.split(";")
            found = (dict(param.split("=", 1) for param in params), value)
            if name == "EXDATE":
                current[name].append(found)
            else:
                current[name] = found
    return events


def ics_text(value: str) -> str:
    """An `.ics` TEXT value, unescaped (RFC 5545 3.3.11).

    Args:
        value (str): as the file writes it.

    Returns:
        str: the text.
    """
    return re.sub(r"\\([\\;,nN])", lambda found: "\n"
                  if found[1] in "nN" else found[1], value)


def ics_time(params: dict, value: str) -> datetime.datetime:
    """An `.ics` DATE-TIME, UTC or in the zone its TZID names.

    Args:
        params (dict): the property's parameters.
        value (str): its value.

    Returns:
        datetime.datetime: the instant, aware.

    Raises:
        SystemExit: a form the export does not use, such as an all-day DATE.
    """
    from zoneinfo import ZoneInfo
    if value.endswith("Z"):
        return datetime.datetime.strptime(
            value, "%Y%m%dT%H%M%SZ").replace(tzinfo=datetime.UTC)
    if "TZID" in params and params.get("VALUE", "DATE-TIME") == "DATE-TIME":
        return datetime.datetime.strptime(
            value, "%Y%m%dT%H%M%S").replace(tzinfo=ZoneInfo(params["TZID"]))
    raise SystemExit(f"{CALENDAR_EXPORT}: no reading for {params} {value}")


def instances(start: datetime.datetime, end: datetime.datetime, rule: str,
              skipped: set) -> list[tuple]:
    """A weekly series' instances, as Google's `singleEvents` expands it.

    Args:
        start (datetime.datetime): the first instance's start, in the
            series' own zone, whose wall clock every instance keeps.
        end (datetime.datetime): its end.
        rule (str): the RRULE.
        skipped (set): the EXDATE instants.

    Returns:
        list[tuple]: `(start, end)` per instance.

    Raises:
        SystemExit: a rule the export does not use.
    """
    parts = dict(part.split("=", 1) for part in rule.split(";"))
    if parts.get("FREQ") != "WEEKLY" or set(parts) - {
            "FREQ", "WKST", "UNTIL", "BYDAY"
    }:
        raise SystemExit(f"{CALENDAR_EXPORT}: no expansion for {rule}")
    days = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
    wanted = {days.index(day) for day in parts["BYDAY"].split(",")}
    until = (ics_time({}, parts["UNTIL"])
             if "UNTIL" in parts else SERIES_HORIZON)
    out, day = [], start.date()
    while (at := datetime.datetime.combine(day, start.timetz())) <= until:
        if day.weekday() in wanted and at not in skipped:
            out.append((at, at + (end - start)))
        day += datetime.timedelta(days=1)
    return out


def calendar_workspace() -> dict:
    """Atlas's calendar, every event of the export, as the gws fake's fixture.

    mirage's base world with the primary calendar made the recorded
    account's: its summary the account's address, as Google names a
    primary calendar, and its zone the one the recordings read. Each event
    keeps the id Google gave it -- its UID less `@google.com`, which is what
    a recorded reply carries -- and a series is stored as the instances
    `singleEvents` expands it into, with the ids Google gives those, since
    that is how the server and the mount both ask for them. The one VEVENT
    with no start, which no import could place, is left out.

    Returns:
        dict: the fixture, in the shape mirage's gws fake reads.
    """
    with zipfile.ZipFile(
            io.BytesIO(
                shown("submodule/mcp-atlas",
                      f"{EXPORTS}/{CALENDAR_EXPORT}"))) as archive:
        [name] = [name for name in archive.namelist() if name.endswith(".ics")]
        text = archive.read(name).decode().replace("\r\n", "\n")
    world = json.loads(shown("submodule/mirage", GWS_BASE))
    [primary] = [row for row in world["calendars"] if row.get("primary")]
    primary.update(summary=re.search(r"^X-WR-CALNAME:(.*)$", text, re.M)[1],
                   timeZone=CALENDAR_ZONE)
    world["calendars"] = [primary]

    def stamp(value: str) -> str:
        """An `.ics` UTC stamp the way Google writes `created`/`updated`."""
        return ics_time({}, value).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def utc(instant: datetime.datetime) -> str:
        """An instant as a UTC dateTime, which the fake renders in the
        calendar's zone."""
        return instant.astimezone(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    world["events"] = []
    for event in ics_events(text):
        if "DTSTART" not in event:
            continue
        start, end = (ics_time(*event[name]) for name in ("DTSTART", "DTEND"))
        base = event["UID"][1].removesuffix("@google.com")
        optional = (("description", "DESCRIPTION"), ("location", "LOCATION"))
        row = {
            "calendarId": primary["id"],
            "status": event["STATUS"][1].lower(),
            "summary": ics_text(event["SUMMARY"][1]),
            **{
                field: ics_text(event[name][1])
                for field, name in optional if name in event
            },
            "created": stamp(event["CREATED"][1]),
            "updated": stamp(event["LAST-MODIFIED"][1]),
        }
        if "RRULE" not in event:
            zone = {
                field: EVENT_ZONES[base]
                for field in ("startTimeZone", "endTimeZone")
                if base in EVENT_ZONES
            }
            world["events"].append({
                "id": base,
                **row, "startDateTime": utc(start),
                "endDateTime": utc(end),
                **zone
            })
            continue
        skipped = {
            ics_time(params, value)
            for params, values in event["EXDATE"]
            for value in values.split(",")
        }
        for first, last in instances(start, end, event["RRULE"][1], skipped):
            world["events"].append({
                "id":
                f"{base}_{first.astimezone(datetime.UTC):%Y%m%dT%H%M%SZ}",
                **row, "startDateTime": utc(first),
                "endDateTime": utc(last)
            })
    return world


def mongo(stack: ExitStack) -> str:
    """A MongoDB up for this run, holding Atlas's `video_game_store`.

    A container per run, restored with `mongorestore` from Atlas's own dump
    as its README restores one, so a write one draw makes is gone before
    the next, as a fresh Atlas sandbox's would be.

    Args:
        stack (ExitStack): removes the container when the run ends.

    Returns:
        str: its connection string, from this machine.

    Raises:
        RuntimeError: it did not come up.
    """
    import tempfile
    import time
    name = f"vfs-bench-mongo-{os.getpid()}-{time.monotonic_ns()}"
    subprocess.run([
        "docker", "run", "--detach", "--rm", "--name", name, "--publish",
        "127.0.0.1::27017", MONGO_IMAGE
    ],
                   stdout=subprocess.DEVNULL,
                   check=True)
    # With its volumes: the image declares two, and `--rm` drops them only
    # when the container stops on its own, not when it is removed by force.
    stack.callback(subprocess.run,
                   ["docker", "rm", "--force", "--volumes", name],
                   capture_output=True)
    with tempfile.TemporaryDirectory() as folder, zipfile.ZipFile(
            io.BytesIO(
                shown("submodule/mcp-atlas",
                      f"{EXPORTS}/{MONGO_EXPORT}"))) as archive:
        archive.extractall(folder, [
            member for member in archive.namelist()
            if member.startswith(f"{MONGO_DUMP}/")
            and not member.endswith(".DS_Store")
        ])
        subprocess.run(
            ["docker", "cp", f"{folder}/{MONGO_DUMP}", f"{name}:/dump"],
            check=True)
    for _ in range(120):
        if subprocess.run([
                "docker", "exec", name, "mongosh", "--quiet", "--eval",
                "db.runCommand({ping: 1}).ok"
        ],
                          capture_output=True).returncode == 0:
            break
        time.sleep(.5)
    else:
        raise RuntimeError("the MongoDB container did not start")
    # `--preserveUUID` keeps each collection's UUID from the dump, which is
    # the order the server lists collections in, and so the recorded order.
    subprocess.run([
        "docker", "exec", name, "mongorestore", "--quiet", "--drop",
        "--preserveUUID", "/dump"
    ],
                   check=True)
    port = subprocess.run(["docker", "port", name, "27017"],
                          capture_output=True,
                          text=True,
                          check=True).stdout.split(":")[-1].strip()
    return f"mongodb://127.0.0.1:{port}/"


def fixture_root() -> Path:
    """Where the fakes find their fixtures, building any not yet built.

    Under `state/`, keyed by both pins they are made from and by this file,
    which builds them, so a bump of either or a change here builds new ones
    rather than serving what an older build left. Each is written
    beside its name and renamed onto it, so a fake started meanwhile, by a
    run beside this one, never reads half a fixture, and a build that dies
    part-way leaves nothing a later run would take for finished.

    Returns:
        Path: the fixture root, holding `notion/atlas.json`,
        `slack/atlas.json`, `gws/atlas.json`, `airtable/atlas.json` and
        `github/atlas.json`.
    """
    built = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    root = (REPO / "state" / "mcpatlas" / pinned("submodule/mcp-atlas")[:12] /
            f"fakes-{pinned('submodule/mirage')[:12]}-{built}")
    for service, build in (("notion", notion_workspace), ("slack",
                                                          slack_workspace),
                           ("gws", calendar_workspace), ("airtable",
                                                         airtable_workspace),
                           ("github", github_workspace)):
        target = root / service / f"{TENANT}.json"
        if not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(f".{target.name}.{os.getpid()}")
            partial.write_text(json.dumps(build()))
            os.replace(partial, target)
    return root


def fake(service: str, stack: ExitStack) -> str:
    """One of mirage's fakes, up for this run and holding Atlas's workspace.

    A process per run rather than the shared stack's, so a write one draw
    makes is gone before the next, as a fresh Atlas sandbox's would be; the
    tenant is seeded again from the fixture before anything reads it.

    Args:
        service (str): `notion`, `slack`, `calendar`, `airtable` or
            `github`, the fake and its launcher.
        stack (ExitStack): stops the fake when the run ends.

    Returns:
        str: the fake's origin.

    Raises:
        RuntimeError: it did not come up.
    """
    from server.seed.papers import close
    integ = REPO / "submodule" / "mirage" / "integ"
    variable = f"{service.upper()}_URL"
    process = subprocess.Popen([
        str(integ / "node_modules" / ".bin" / "tsx"),
        str(REPO / "server" / "fakes" / f"{service}_api.mjs"), "--fixture",
        TENANT, "--fixture-root",
        str(fixture_root())
    ],
                               cwd=integ,
                               stdout=subprocess.PIPE,
                               text=True)
    stack.callback(close, process)
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        if not selector.select(timeout=300):
            raise RuntimeError(f"the {service} fake did not start")
        line = process.stdout.readline().strip()
    if not line.startswith(f"{variable}=http://127.0.0.1:"):
        raise RuntimeError(f"the {service} fake failed to start: {line}")
    url = line.split("=", 1)[1]
    request = urllib.request.Request(
        f"{url}/reset",
        data=json.dumps({
            "tenants": [TENANTS.get(service, TENANT)],
            "fixture": TENANT
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(request, timeout=300) as reply:
        json.load(reply)
    return url
