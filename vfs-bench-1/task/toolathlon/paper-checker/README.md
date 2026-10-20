# Paper checker

Check a LaTeX draft for citation and reference issues across several `.tex`
files and a `.bib` bibliography — verify every `\cite{}`, `\label{}`, `\ref{}`
and `\autoref{}` resolves, and fix the broken ones to the correct names.

Both arms start from a single `files.tar.gz` and edit the files where the
grader reads them. The grader looks for `<agent_workspace>/my_paper`. The
brief does not say where to leave the extracted tree.

Two mirage `tar` defects are why the Python route for extraction
is the one `SKILL.md` points at: `tar -c` calls `read_bytes` on every
operand with no `isdir` check, so it can only archive plain files, and `-C`
is not honoured. `tarfile.add(dir, arcname=...)` does its own recursive walk
and routes around both.

```bash
uv run python agent/run_agent.py toolathlon/paper-checker --tools vfs
uv run python agent/run_agent.py toolathlon/paper-checker --tools mcp
```
