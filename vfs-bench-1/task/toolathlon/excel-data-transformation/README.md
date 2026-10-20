# Excel data transformation

Convert `Household_Appliances.xlsx` from a two-dimensional layout — refrigerator,
air-conditioner and washing-machine sales in separate column groups — into the
one-dimensional shape `Format_Example.xlsx` demonstrates, and save it as
`Processed.xlsx`. Reverse chronological from December 2024, months with no data
omitted, unknown fields left blank.

`vfs/SKILL.md` documents openpyxl; the pyodide runtime seeds the wheels
itself, so the prompt is just `import openpyxl`.

Caveat: `local-python-execute` shells out to `uv run --directory
<agent_workspace>`, and uv finds its project by walking up. Upstream that lands
on `/workspace/pyproject.toml` and the synced Toolathlon environment; here the
scratch directory sits under this repo, so it walked up to ours and the
interpreter came up bare. `run_agent.py` sets `UV_PROJECT` to the checkout to
restore it.
