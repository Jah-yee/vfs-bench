# Set the camera-ready deadline reminder

Eighteen emails arrived over the last six days. One of them moves the COML
main-track camera-ready deadline. Put a reminder in the calendar three hours
before it.

## Python runtime correction

The VFS workspace now uses Pyodide with pinned timezone data. Monty could
not execute ordinary `datetime.astimezone()` and `zoneinfo` calculations
seen in the agent traces. This changes the VFS Python runtime; the original
MCP handlers, fixtures and graders are unchanged.

Live checks passed for named-zone and fixed-offset conversions, daylight
saving time, mounted mailbox reads, and Python writes read back by the shell.

## The fixture had to be re-dated

Upstream's mailbox is frozen: every message is dated September 2025 and
`groundtruth_workspace/today.txt` says `2025-09-15`. Nothing regenerates
either, and the evaluator does not mind, because it computes the expected
deadline as `today.txt + 11 days` rather than from a clock.

The **task statement** minds. "Check my emails from the past day" is false
about a mailbox a year old.

That is a fixture measuring incuriosity, so
[`shared/seed_db.py`](shared/seed_db.py) moves every date in it by one
constant: the last day of mail becomes today, `today.txt` becomes today, and
every interval inside the mailbox is exactly what upstream wrote — the six
days it spans, the eleven between the extension and the deadline it
announces, the gaps between the distractors. Both arms get the same re-dated
mailbox, and no message is otherwise altered.

## Which deadline

Seven of the eighteen messages carry a date, and six of them are wrong
answers:

| | says | why not |
|---|---|---|
| COML camera-ready | day 4 of the fixture, 23:59 AoE | superseded |
| **COML camera-ready** | **day 11, 23:59 AoE** | **the extension — the answer** |
| COML video recording | day 10, 23:59 AoE | a different deliverable |
| COMLW camera-ready | "tomorrow" | the workshop, not the main track |
| COAI camera-ready | day 7, 23:59 AoE | a different conference |
| COLM camera-ready | day 5, 23:59 AoE | a different conference, one letter apart |
| LCFM reviews | day 8, AoE | not a camera-ready at all |

The reminder goes three hours earlier, 20:59 AoE, and the grader allows five
minutes.

## Two servers, one calendar

Toolathlon points its calendar server at a real Google account. Here both
arms read and write mirage's mock Google Workspace server, the same one the
sheets tasks use:

* the mirage arm through the `gws calendar` CLI, whose `apiBase` is the
  mock;
* the MCP arm through upstream's own
  `@gongrzhe/server-calendar-autoauth-mcp`, unmodified and pinned by
  [`server/mcp/setup_calendar.py`](../../../server/mcp/setup_calendar.py), with
  [`redirect/gws_calendar/calendar_hook.mjs`](../../../redirect/gws_calendar/calendar_hook.mjs) giving every
  googleapis call a `rootUrl` on the mock. That is one merged option per
  call and nothing else: the server's five tools, their schemas and their
  error text are as published.
* the evaluator through *the same* pinned server, because
  `setup/toolathlon/setup_toolathlon.py` rewrites `configs/mcp_servers/google_calendar.yaml`
  to run it. It also raises the session timeout, which upstream sets to ten
  seconds — enough for a warm `npx` and not for a cold one.

Its OAuth is two files of fake credentials in
[`redirect/gws_calendar/`](../../../redirect/gws_calendar/README.md); the mock
takes any bearer token.

## Original Google tool CLI — 2026-09-13

The current interface is `google-calendar <original-tool-name>` with one JSON argument object. It invokes the pinned original MCP handlers and preserves their schemas, defaults and responses. The broad `gws` registration has been removed. The Calendar CLI has exactly five commands.

Live read/write and schema parity checks passed. `tests/parity.py` checks this CLI's commands against the server's tools on every run.
