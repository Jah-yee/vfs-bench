# Interview report

Read candidate résumés (`Candidates_resumes.docx`) and interviewer evaluations
(`Interviewer_evaluation.docx`), produce one Word evaluation report per
candidate following `Format.md`, and write `recommend.txt` containing only the
best candidate's name.

The mirage backend used to drop stderr whenever a command exited 0, which a
pipeline always does, so a failing `python-docx` call inside `... | tail`
looked like success. stderr is now returned.

```bash
uv run python agent/run_agent.py toolathlon/interview-report --tools vfs
uv run python agent/run_agent.py toolathlon/interview-report --tools mcp
```
