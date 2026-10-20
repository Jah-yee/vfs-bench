# Student interview scheduling

Ninety-four emails are in the professor's inbox, twenty of them student
applications. Interview only the students with independent first-author
publications; fit each of them ninety minutes over the next two days,
between 08:00 and 17:00 Hong Kong time, around the two meetings already on
the calendar.

## Python runtime correction

The VFS workspace now uses Pyodide with pinned timezone data. Monty could
not execute ordinary `datetime.astimezone()` and `zoneinfo` calculations
seen in the agent traces. This changes the VFS Python runtime; the original
MCP handlers, fixtures and graders are unchanged.

Live checks passed for named-zone and fixed-offset conversions, daylight
saving time, mounted mailbox reads, and Python writes read back by the shell.

Two local setup defects were found and fixed:

- The calendar seeder still sent `calendarTimeZone` as a top-level reset
  field. The pinned Mirage fixture expects it inside `extras`. The adapter
  now uses that existing API shape; a live check verified unchanged meeting
  times and the Hong Kong timezone.
- The confined Calendar MCP launcher could not read its `file://` import
  hook. Its exact hook file is now explicitly readable. The original server,
  arguments and tool schemas are unchanged; confined startup and all five
  Calendar tool definitions were checked.

The missing Calendar package was also installed from the committed npm
lock.

## Which applicants qualify

Three of the twenty applicants qualify. Two of them say so like this:

```
Publications:  First Author : "Deep Learning for NLP", ICML 2023
```

and the third says:

```
Research Results:  Sole Author : "Advanced Object Detection in Complex
                   Scenes", CVPR 2023
```

## One calendar, two clients

Toolathlon points its calendar server at a real Google account. Here both
arms read and write mirage's mock Google Workspace server: the mirage arm
through the `gws calendar` CLI, the MCP arm through upstream's own pinned
`@gongrzhe/server-calendar-autoauth-mcp` with
[`redirect/gws_calendar/calendar_hook.mjs`](../../../redirect/gws_calendar/calendar_hook.mjs) redirecting its
`rootUrl`, and the evaluator through that same pinned server. See
[set-conf-cr-ddl](../set-conf-cr-ddl/README.md), which sets it up.

## Nothing needed re-dating

Unlike [set-conf-cr-ddl](../set-conf-cr-ddl/README.md), whose mailbox is
frozen in a committed file, this preprocess is written against the clock:
it stamps `today.txt` from `datetime.now()` and places every message at a
seeded offset from that. "Tomorrow and the day after" mean what they say on
the day it runs, so [`shared/seed_db.py`](shared/seed_db.py) runs upstream's
own preprocess unchanged and replaces only the calendar half — the same two
meetings, against the mock instead of Google.

## Original Google tool CLI — 2026-09-13

The current interface is `google-calendar <original-tool-name>` with one JSON argument object. It invokes the pinned original MCP handlers and preserves their schemas, defaults and responses. The broad `gws` registration has been removed. The Calendar CLI has exactly five commands.

Live read/write and schema parity checks passed. `tests/parity.py` checks this CLI's commands against the server's tools on every run.
