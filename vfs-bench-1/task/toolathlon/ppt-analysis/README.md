# PPT analysis

Study `Compile.pptx` on behalf of a student who missed the lecture and write
`NOTE.md`: summarize functional versus imperative symbol tables and how their
insertion operations differ, reproduce every code listing from the deck with an
explanation, and explain the homework in `HW.PDF`.

Toolathlon gives this task both the `pptx` and `pdf` servers
plus `filesystem` and `terminal`.

```bash
uv run python agent/run_agent.py toolathlon/ppt-analysis --tools vfs
uv run python agent/run_agent.py toolathlon/ppt-analysis --tools mcp
```
