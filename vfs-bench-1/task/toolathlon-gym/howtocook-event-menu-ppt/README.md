# Howtocook event menu ppt

> I am organizing a company team-building dinner event and need your help
> planning the menu. […] create a PowerPoint presentation called
> `Event_Menu_Presentation.pptx` […] create an Excel file called
> `Menu_Budget.xlsx`.

Browse a 322-recipe Chinese home-cooking corpus, pick an appetizer, a main
and a dessert, and write two documents: a five-slide deck and a two-sheet
workbook counting ingredients and difficulty.

## The surface

| server | tools | what it is |
|---|---:|---|
| pptx | 37 | GYM's vendored Office-PowerPoint-MCP-Server |
| excel | 25 | GYM's vendored excel-mcp-server |
| filesystem | 14 | the reference server, scoped to the workspace |
| howtocook | 5 | GYM's vendored 0.1.1 |
| local | 14 | Toolathlon's local-tool layer — see below |
| **total** | **95** | |

Against **one** on the mirage side: a shell. Two of these servers are
document builders that expose a tool per operation, and every one of their
schemas rides in every request.

**Eight of those 14 local tools are ours, not GYM's.** GYM's harness resolves
this task's five declared names to six tools; Toolathlon's resolves them to
fourteen. The gap is `manage_context` (3 tools against 1 stub) and `history`
(5 against 1). It lands entirely on the arm being measured against, and
[`task/toolathlon-gym/README.md`](../README.md) says what closing it would
take.

## Both arms read the same corpus

`tests/parity.json`, three cases, all agreeing: 322 dishes, the same names in
`水产`, the same ingredient list for one dish. The MCP server imports
`build/data/all_recipes.json` and mirage's `cook` CLI is pointed at the same
file, so this compares two clients over one corpus rather than two copies.

    uv run python tests/parity.py howtocook-event-menu-ppt

That agreement is not free. GYM's howtocook 0.1.1 fetches
`https://weilei.site/all_recipes.json` first and only falls back to the
committed file — so on a networked machine the two arms would read different
corpora, and the tool *schema* would differ too, since
`getRecipesByCategory` builds a `z.enum` from whatever loaded. The builder
starts it behind `NO_NETWORK`, and the server confirms the fallback on
startup: `获取远程菜谱数据失败，将使用本地备份数据`, then `已加载 322 个菜谱`.

## Running it

    uv run python agent/run_agent.py toolathlon-gym/howtocook-event-menu-ppt --tools vfs
    uv run python agent/run_agent.py toolathlon-gym/howtocook-event-menu-ppt --tools mcp

No stack. `needs_stack` reads the task's own declaration and none of its four
servers keeps state outside the run's workspace, so a draw starts no Docker.
The seeder empties the workspace and runs upstream's `preprocess/main.py`,
which for this task removes leftover deliverables — the exact shape that
would otherwise let an arm pass on the previous arm's answer.

Setup this task needs beyond `setup/setup.py`'s usual: GYM's `howtocook` has
to be built (`npm install && npm run build`, now a step in that script), and
the wheels have to be there.
