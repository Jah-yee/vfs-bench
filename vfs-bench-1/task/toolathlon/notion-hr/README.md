# Notion HR record

Read ten resumes out of the workspace, fill the `Candidates` table on a Notion
page from them, delete the two sample rows already there, and email a fixed
rejection template to exactly those applicants whose applied position is not
hiring.

## Two harness defects

**pypdf could not read one resume.** `michael_diaz_resume.pdf` is drawn in
box-drawing characters, and its content lines contain no space glyphs at all —
words are separated by advancing the text cursor one 6.6pt monospace cell.
The gaps either side of the dash measure 6.61pt and 6.60pt, and pypdf renders
one as a space and the other as nothing:

```
pypdf, plain:    │ RiceUniversity- JonesGraduateSchoolofBusiness │
pypdf, layout:   │ RiceUniversity-JonesGraduateSchoolofBusiness  │
pymupdf:         │ Rice University - Jones Graduate School of Business │
```

That lone space is worse than dropping both, because it is evidence for a
tokenisation — the wrong one. The MCP arm reads the same file through
`pdf-tools`, which is PyMuPDF underneath and gets it right. `task/toolathlon/script/setup_pyodide_packages.py` now vendors pyodide's
wasm pymupdf, so both arms read identical bytes. Across all 173 PDFs in the
suite this file is the only outlier — 70 glued word pairs against pymupdf's 5,
where a normal academic PDF sits at 129 against 126.

**And the workspace had no `/tmp`.** Every workspace now mounts a ram-backed
`/tmp`.

## Where the task comes from

Upstream seeds this task by duplicating a page out of a live Notion account
(`preprocess/main.py` → `notion_remove_and_duplicate`), which cannot run
against a mock. The page it copies is public and named in Toolathlon's own
setup guide, so the fixture is derived rather than invented:
[`shared/author_fixture.py`](shared/author_fixture.py) reads the `HR Record`
subpage of that template through notion.site's record API and rewrites it into
the shape mirage's fake seeds from, keeping every id, property id, column and
cell. `--check` re-verifies the committed JSON against the live template.

Three databases come across. `Job Positions` is the one that carries the task:
its `Head Counts` column is 0 for `Securities Trader` and `Portfolio Manager`,
which is what makes four of the ten applicants — and only those four —
rejection cases. `Candidates` ships two `Example` rows to delete and one real
row, Alice Jackson, whose `Highest Degree` reads `bachelor` where her resume
says master, so the task is an edit as well as an append.

Both arms read one fake: `bin/start.sh up` runs mirage's Prisma-backed
Notion server, the mirage arm reaches it through the `notion` mount and the `notion` CLI,
and the MCP arm through `@notionhq/notion-mcp-server` with `BASE_URL` pointed
at it. No request shim is needed on either side.

The evaluator's failure message can name a *position* mismatch, such as
Michael Diaz's (`INVESTMENT ANALYST` for `Investment Analyst`). That is a red
herring: the pass/fail comparison lowercases position, degree and school
(`evaluation/main.py:198`), and only the explanation strings re-compare
case-sensitively. Emily James is `SECURITIES TRADER` in the same table and
passes silently.

## What the fake had to fix first

Before mirage `7fbe3aedb` (#747), the MCP arm could not be graded, because
the fake made deletion impossible from the API side while leaving mirage's own CLI able to do it:

```
DELETE /v1/blocks/<row>                → HTTP 404  "Could not find route"
PATCH  /v1/pages/<row> {archived:true} → HTTP 200  archived=true, in_trash=false
POST   /v1/databases/<db>/query        → still returns the row
```

`API-delete-a-block` is the only tool in the arm's 19 named for deletion, and
there was no `DELETE` route. The fallback, `API-patch-page` with `archived:
true`, returned 200 and changed nothing the grader could see, because
`archived` and `in_trash` were two stored columns and only `in_trash` was
filtered. `ntn pages trash` sets `in_trash`, so the mirage arm deleted rows
without trouble and the MCP arm could not delete one at all.

#747 adds the route, collapses the two columns into one bit with both
spellings on the wire, and puts a database row's cells in its `page.json`
under `properties`. All three are verified here: `DELETE` now returns 200 and
the row leaves the query, a `PATCH` of `archived` does the same, and `cat` on
a row shows its cells.

## A caveat about the mirage arm generally

Bumping `submodule/mirage` does **not** rebuild the TypeScript packages, and
`agent/workspace.py` starts the daemon out of `packages/server/dist/` with no
freshness check. Any mirage measurement is of whatever was last built, not of the
pinned commit, so `pnpm build` belongs beside every pin bump.

## Running it

```bash
bin/start.sh up &                                  # fake Notion
bin/start.sh up &                                    # GreenMail
uv run python server/mcp/setup_notion.py                  # once, for the MCP arm
uv run python task/toolathlon/notion-hr/shared/seed_notion.py    # before every run

uv run python agent/run_agent.py --task-dir task/toolathlon/notion-hr --tools vfs
uv run python agent/run_agent.py --task-dir task/toolathlon/notion-hr --tools mcp
```

The MCP arm wants the default 60-turn cap; 40 truncates it.

A golden solver drove the whole task through `ntn` and `himalaya` along a
fixed path and graded `Pass all tests!`, which is what establishes that the environment is solvable.
