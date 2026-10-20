---
name: workspace-commands
description: The shell commands and task tools available in this workspace.
---

# Available commands

Python (`python` or `python3`), Perl, JavaScript/Node.js, and TypeScript
runtimes are unavailable. Use the shell commands and task CLIs documented
below; do not probe for or attempt to install other runtimes.

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## howtocook

Use `howtocook <command> '<JSON arguments>'`. Run
`howtocook <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `howtocook getAllRecipes` | `{no_param?: str}` | 获取所有菜谱 — `no_param`: 无参数 |
| `howtocook getRecipesByCategory` | `{category: "水产" \| "早餐" \| "调料" \| "甜品" \| "饮品" \| "荤菜" \| "半成品加工" \| "汤" \| "主食" \| "素菜"}` | 根据分类查询菜谱，可选分类有: 水产, 早餐, 调料, 甜品, 饮品, 荤菜, 半成品加工, 汤, 主食, 素菜 — `category`: 菜谱分类名称，如水产、早餐、荤菜、主食等 |
| `howtocook recommendMeals` | `{allergies?: list[str], avoidItems?: list[str], peopleCount: int}` | 根据用户的忌口、过敏原、人数智能推荐菜谱，创建一周的膳食计划以及大致的购物清单 — `allergies`: 过敏原列表，如["大蒜", "虾"]; `avoidItems`: 忌口食材列表，如["葱", "姜"]; `peopleCount`: 用餐人数，1-10之间的整数 |
| `howtocook whatToEat` | `{peopleCount: int}` | 不知道吃什么？根据人数直接推荐适合的菜品组合 — `peopleCount`: 用餐人数，1-10之间的整数，会根据人数推荐合适数量的菜品 |
| `howtocook getRecipeById` | `{query: str}` | 根据菜谱名称或ID查询指定菜谱的完整详情，包括食材、步骤等 — `query`: 菜谱名称或ID，支持模糊匹配菜谱名称 |
