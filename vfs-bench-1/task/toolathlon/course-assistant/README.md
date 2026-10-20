# Course assistant

The runner now restores the upstream JSONL inbox automatically, preserves student account addresses, uses the original TA account, and supplies the upstream clock and single-turn instruction to both arms.

Cross-reference an NLP course gradebook (`nlp_statistics.xlsx`) against the
presentation submissions sitting in the TA's inbox, work out which students are
missing something, and email each of them under the subject
`nlp-course-emergency`.

The task is a two-source join, and the three students who should be mailed
qualify two different ways:

| student | why |
|---|---|
| Steven Morgan | no presentation email in the inbox |
| Carolyn Alvarez | `Assignment10 = miss` in the spreadsheet |
| Michelle Brooks | `Assignment7 = miss` — but she *did* send a presentation |

Two students must **not** be mailed despite empty rows: Sandra Miller (`Note:
Already withdrew from the course`) and Andrew Moore (`Note: Auditing teacher`).
So the sheet carries three distinct empty-ish states — a literal `miss` string,
a blank cell excused by the `Note` column, and a blank `Pre` column that means
nothing because presentations arrive by email.

The pyodide runtime takes a `sysPath` and the yaml declares
`/opt/wheels/*.whl`, so `import openpyxl` is the whole command.

`nlp_statistics.xlsx` is a zip container, so this arm is the TypeScript one:
`monty` lacks zlib, `local` cannot see the mounts, and pyodide has it.
`vfs/workspace.yaml` carries camelCase email keys, because the TypeScript
`himalaya` CLI rejects the snake_case its own email resource accepts. Fixed
upstream by mirage #724.

Caveat: both arms and the grader talk to **GreenMail** on Toolathlon's ports
rather than upstream's poste.io. `server/seed/seed_mail.py` **resets the whole server by
default**, so a run wipes the previous run's sent mail — grade each arm before
starting the next.

```bash
bin/start.sh up
uv run python agent/run_agent.py --task-dir task/toolathlon/course-assistant --tools vfs
```
