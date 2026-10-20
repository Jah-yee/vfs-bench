# Music analysis

Read `Billboard Pop Chart by Year` from Google Drive, compute each song's
longest consecutive run on the chart, and write one sheet per year into
`music_analysis_result.xlsx` in the workspace.

The fixture is real rather than captured. Upstream copies a live Google Sheet
by URL, which needs the network; the same workbook is vendored in the task's
groundtruth, so `shared/seed_mock.py` reads it host-side with openpyxl and seeds
the mock GWS directly — **56 tabs, 33,587 rows**, nothing trimmed. It renders as
a **41 MB** `.gsheet.json` on the mount (the NHL fixture's was 1.3 MB), and the
mount does not page, so `cat` is not an option and the agent has to `jq` it.

**The 1942 sheet is a defect in the task, not in the arm.** The tab holds 86
song rows, a stray date cell, then a **second table titled `Top 20 of 1942`**.
Ground truth's `analyze_music.py` stops at the first row with a song but no
artist:

```python
if pd.isna(row.iloc[1]) or row.iloc[1] == '':
    if seen_song_rows:
        break
```

The task statement never says that, and says each sheet "should contain all
songs". An arm that reads the sheet literally gets 106 rows and is marked wrong
for following the brief.

The output is an xlsx — a zip container — and no Python-side runtime can open
one: `monty` lacks zlib and `local` cannot see the mounts. mirage's
TypeScript `pyodide` runtime is Emscripten CPython and does have zlib, so this
task runs through [`agent/workspace.py`](../../../agent/workspace.py) with
`vfs/workspace.yaml`. `/opt/wheels` mounts the vendored pure-Python wheels
and the runtime's `sysPath` puts them on `sys.path` at every mount sync; a
wheel goes on the path directly, since zipimport reads it in place.

`local-python-execute` used to resolve to a bare interpreter — `uv run` walks
up to find its project, and here it found this repo rather than the Toolathlon checkout. `run_agent.py` now sets `UV_PROJECT`.

```bash
bin/start.sh up
uv run python agent/run_agent.py toolathlon/music-analysis --tools vfs
uv run python agent/run_agent.py toolathlon/music-analysis --tools mcp
```

The run reseeds the fake Drive first, which this task needs: the fixture
lives in the folder rather than in files, so the second arm has to start
from the folder the first one started from. `server/seed/seed_task.py` runs
`shared/seed_mock.py` because `task.json` declares it. By hand it is:

```bash
uv run --with openpyxl python \
    task/toolathlon/music-analysis/shared/seed_mock.py     # prints folder_id
uv run python agent/run_agent.py \
    --task-dir task/toolathlon/music-analysis --tools vfs
```
