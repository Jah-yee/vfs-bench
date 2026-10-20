# Sales accounting

Today is 18 January 2024. Add to the account book only the transaction records
held in the agent's memory from exactly last week and the week before last —
excluding anything from the current week.

The task says the records are "in your memory" and Toolathlon wires a `memory`
server for it. mirage has no equivalent and reads the same content off the mount.

```bash
uv run python agent/run_agent.py toolathlon/sales-accounting --tools vfs
uv run python agent/run_agent.py toolathlon/sales-accounting --tools mcp
```
