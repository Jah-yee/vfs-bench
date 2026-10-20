# Course schedule

Pick this student's classes for the semester out of a timetable and a master
exam table, then write the exams they will sit to `exam_schedule.jsonl`,
sorted by when they start. Who the student is — their id, their department,
their English score — is in Memory.

## Nothing here is a service

Five MCP servers are mounted and none of them talks to anything:

- **memory** is a local JSON store. Its whole state is
  `memory/memory.json`, which Toolathlon copies into the agent workspace, so
  the mirage arm reads the same file off `/work`. It is pinned by
  [`server/mcp/setup_memory.py`](../../../server/mcp/setup_memory.py) — upstream ran
  it as `npx -y`, and the version decides the tool surface.
- **excel**, **pdf-tools** and **filesystem** are reading two files that are
  already in the workspace.
- **fetch** is not needed. The task declares it and needs nothing from the
  web, but declaring it is what puts four more tool schemas in front of the
  model on every request. It is mounted, with an empty capture
  (`shared/web_fixture.json`), so a URL an agent invents misses and says so
  rather than reaching the internet. See
  [`capture_web.py`](../script/capture_web.py) for the capture machinery.

## What the task turns on

**The rooms** are the part of the task that needs Memory. Two of the four
courses are examined in several rooms at once — three for 新时代, two for
算法 — and the table splits them by student id in its 备注 column,
`2401210472-2401210655`. This student is 2401210477, and in both cases they
are not in the first room listed.

**The course name** is where the two documents disagree. 郁莲 teaches
classes 01 and 02 of 算法分析与设计, and class 02 is in the evening, so the
answer is class 01 — but the exam table sits 01 and 02 together and calls
that row `算法分析与设计-01、02班`. The task says all information must
match the Excel file, and the ground truth uses the Excel name.

The task otherwise turns on four decisions: the evening class is dropped
(自然辩证法概论 2班, 算法 02班),
the department picks one of five 综合实践 classes, the major picks between
two identically-named 新时代 exams, and an English score of 88 is over the
70 that exempts, so 英语 produces no exam at all.
