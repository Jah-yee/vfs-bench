# Reimbursement form filler

Extract the filename, billing month and amount from every taxi receipt PDF in
`bills/` covering the last three months, fill them into `Bill_Format.xlsx`
following the rules in `requirement.txt`, and save the result as
`department_expenses.xlsx` without changing the original layout.

```bash
uv run python agent/run_agent.py toolathlon/reimbursement-form-filler --tools vfs
uv run python agent/run_agent.py toolathlon/reimbursement-form-filler --tools mcp
```
