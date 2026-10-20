# NHL back-to-back analysis

Count each team's back-to-back sets in the NHL 2024–25 schedule (1,312 games in
a Google Sheet), split by home/away configuration, into a new spreadsheet
`NHL-B2B-Analysis` with headers `Team,HA,AH,HH,AA,Total`.

In the NHL parity cases, six agreed, and the existing
`create_spreadsheet` ID difference remains (`f0003` versus `sheet0001`).
It did not affect the grader. Across NHL, apply-phd-email and yahoo-analysis,
the suite reports 18 agreements, zero failures and that one known divergence.

The CLI holds only the ten verbs that mutate. `mcp-google-sheets` exposes
nineteen tools, nine read-only, and an earlier version mirrored all of them.
`ls`, `cat`, `jq` and `grep` answer those nine, so they are gone.

Caveat: only mirage's surface was trimmed. The MCP arms still carry their nine
read tools plus the filesystem and terminal servers.

## Reproducing

```bash
bin/start.sh up
uv run python agent/run_agent.py toolathlon/nhl-b2b-analysis --tools vfs
uv run python agent/run_agent.py toolathlon/nhl-b2b-analysis --tools mcp
```

The batch reseeds the fake Drive between arms by running
`shared/seed_mock.py`, which it now does for the same reason it already ran
`shared/seed_db.py`: the second arm has to start from a folder holding only
`NHL 2425 Schedule`, not from one that already holds the first arm's answer.

`DRIVE_FOLDER_ID` no longer has to be exported by hand. The default used to
live in one arm's branch of [`agent/run_agent.py`](../../../agent/run_agent.py)
where the others never saw it, and a workspace interpolating the name straight
out of `vfs/workspace.yaml` died on `missing environment variables:
['DRIVE_FOLDER_ID']` before building. It is set for all three
surfaces now, to the same `f0001`, so no arm is given a folder the others do
not have.
