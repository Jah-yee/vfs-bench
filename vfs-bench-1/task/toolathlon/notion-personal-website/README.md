# Notion personal website

Read a 142-paragraph docx and transcribe it into the five empty sections of a
Notion page — About Me, Paintings, Workshop, Prizes, Exhibitions — losing
nothing. The grade is substring presence over about 200 required strings.

## Where the task comes from

Upstream seeds this task the way it seeds every notion task: `preprocess/
main.py` calls `notion_remove_and_duplicate --needed_subpage_name "Colley
Whisson"`, which copies a subpage out of a live account. One public template
holds the source page for all eight, and it is named in Toolathlon's own setup
guide, so the fixture is derived rather than invented:
[`shared/author_fixture.py`](shared/author_fixture.py) reads that subpage
through notion.site's record API and rewrites it into the shape mirage's fake
seeds from, keeping every block id and every character. `--check` re-verifies
the committed JSON against the live template.

The page that comes across is eight blocks: six section headers with their
emoji, an introduction, and one placeholder line under About Me. There are no
databases, which is what makes this the cheapest notion task to port — the
whole fixture is 1 page and 8 blocks.

`colley_whisson.docx` arrives from upstream's `initial_workspace`, which
`run_agent.py` copies into the agent workspace for both arms. It is 142 flat
paragraphs with no heading styles at all: the sections are marked only by
three bare lines reading `Workshop`, `Prizes` and `Exhibitions`, and the
About Me / Paintings boundary is not marked at all.

## The lookahead that eats a section

The evaluator splits the page into sections with one regex per section
(`evaluation/check_remote.py`):

```python
r'#\s*[📰📌]*\s*Work?[Ss]hop\s*(.*?)(?=#|$)'
```

`(?=#|$)` ends the section at **the next `#` character anywhere in the page**.
So a section that contains any sub-heading stops at that sub-heading and
everything below it is scored as missing.

The Workshop material in the docx is the one part with real internal
hierarchy: a `2025` line and then six venues. Rendered faithfully —

```
# 📰 Workshop
## 2025
### MacKay Art Society (Beaconsfield, Queensland)
...
```

— the Workshop capture ends at `## 2025`, four characters in.

A golden solver passed, `Pass all tests!`, by writing every line as a flat
paragraph under the six original headers. So the environment is solvable and the fixture and evaluator agree — an agent
just has to guess that structure is penalised, which nothing in the task
statement says.

This is upstream's own behaviour, not something the port introduced: the same
regex runs against real Notion, and both arms meet it equally. It is recorded
rather than fixed, because the task statement is copied byte-for-byte and
editing it would break comparability.

## Running it

```bash
bin/start.sh up &                                              # fake Notion
uv run python server/mcp/setup_notion.py                              # once, for the MCP arm
uv run python task/toolathlon/notion-personal-website/shared/seed_notion.py  # before every run

uv run python agent/run_agent.py --task-dir task/toolathlon/notion-personal-website --tools vfs
uv run python agent/run_agent.py --task-dir task/toolathlon/notion-personal-website --tools mcp
```

Re-seeding before every run is not optional: the task rewrites the page's own
blocks in place, so a second run would start from the first run's answer.

The evaluator needs the res_log stub `task/toolathlon/script/grade_task.py` passes, and the
same `PYTHONPATH`/`NOTION_URL`/`NOTION_TOKEN` shim every notion task uses:

```bash
(cd submodule/Toolathlon && env PYTHONPATH=../task/toolathlon/notion-personal-website/toolathlon/eval_shim \
   NOTION_URL=http://127.0.0.1:5091 NOTION_TOKEN=notion-personal-website \
   uv run -m tasks.finalpool.notion-personal-website.evaluation.main \
   --res_log_file /tmp/stub.json --agent_workspace <ws>)
```
