# Detect revised terms

Read `new_law.pdf` and a set of case judgment documents, and identify every
cited clause whose *substantive* content differs from the corresponding
provision in the new law — changes to the rule, scope, condition or legal
effect. Clauses merely renumbered or relocated do not count, and only clauses
the judgment actually quotes are in scope.

Ground truth has 9 rows.

```bash
uv run python agent/run_agent.py toolathlon/detect-revised-terms --tools vfs
uv run python agent/run_agent.py toolathlon/detect-revised-terms --tools mcp
```
