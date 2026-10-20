# experiments-recordings

Record Guru benchmark maxima and the best average step in the original
Notion database.

Both arms read the captured `mbzuai-llm/Guru` project: 8 runs and 1,483 full
history rows, with observed sampled-history responses retained. The complete
file catalog is captured; large file bodies are fetched on demand only if
their recorded MD5 and byte length still match. A changed file fails closed.

The public Notion source contains 17 columns and two blank rows. The capture
keeps the public API responses and source hashes; a deterministic producer
renders the page, child database and rows for Mirage’s fixture. This replaces
upstream’s browser-based page duplication with source restoration. No live
Notion account is modified. Fixture identity metadata uses the existing
Notion fixture defaults; source titles, schema, rows and hierarchy are retained.

Each run owns fresh Notion and W&B API fixtures. The original Notion MCP
server and W&B MCP dependency trees are pinned. The original grader reads the
same APIs; its page ID file points at the restored page for the run.

DVC stages: `capture-guru`, `guru-capture-environment`,
`capture-experiments-notion`, and `derive-experiments-notion`.
The Guru receipt retains the lockfile from its actual capture environment.

API inventory checks confirmed 17 Notion columns, 2 rows and 8 W&B runs.
No test files were added.

Build Mirage and its integration dependencies, and generate the Notion client:

```sh
cd submodule/mirage/integ
INTEG_DB_URL=file:/tmp/notion-generate.db pnpm exec prisma generate --schema prisma/notion.prisma
cd ../../..
uv run python agent/run_agent.py toolathlon/experiments-recordings --tools mcp
uv run python agent/run_agent.py toolathlon/experiments-recordings --tools vfs
uv run dvc status
```

An earlier Mirage revision preloaded every mounted file before Python
execution, and a replay stalled while sweeping Guru's roughly 47,000-file
catalog, even for Python that only read Notion. This is fixed for the Node
worker runtime. Commit `b867c8363b` introduced lazy filesystem access; PR
#1048 includes it, and the current Mirage pin `7e93d2f5c1` contains that change.
On September 10, all 14 existing Pyodide lazy-worker tests passed, including
reading Notion without touching an unrelated 47,000-file W&B mount.
The inline fallback for environments without worker support still preloads;
that is not the normal Node path used here.
