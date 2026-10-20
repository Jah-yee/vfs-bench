---
name: workspace-commands
description: The shell commands, task tools, and python3 interpreter available in this workspace.
---

# Available commands

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip  curl

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## excel

Use `excel <command> '<JSON arguments>'`. Run `excel <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `excel apply-formula` | `{filepath: str, sheet_name: str, cell: str, formula: str}` | Apply Excel formula to cell. Excel formula will write to cell with verification. |
| `excel validate-formula-syntax` | `{filepath: str, sheet_name: str, cell: str, formula: str}` | Validate Excel formula syntax without applying it. |
| `excel format-range` | `{filepath: str, sheet_name: str, start_cell: str, end_cell?: str = null, bold?: bool = false, italic?: bool = false, underline?: bool = false, font_size?: int = null, font_color?: str = null, bg_color?: str = null, border_style?: str = null, border_color?: str = null, number_format?: str = null, alignment?: str = null, wrap_text?: bool = false, merge_cells?: bool = false, protection?: dict = null, conditional_format?: dict = null}` | Apply formatting to a range of cells. |
| `excel read-data-from-excel` | `{filepath: str, sheet_name: str, start_cell?: str = "A1", end_cell?: str = null, preview_only?: bool = false}` | Read data from Excel worksheet with cell metadata including validation rules. Args: filepath: Path to Excel file sheet_name: Name of worksheet start_cell: Starting cell (default A1) end_cell: Ending cell (optional, auto-expands if not provided) preview_only: Whether to return preview only Returns: JSON string containing structured cell data with validation metadata. Each cell includes: address, value, row, column, and validation info (if any). |
| `excel write-data-to-excel` | `{filepath: str, sheet_name: str, data: list[list], start_cell?: str = "A1"}` | Write data to Excel worksheet. Excel formula will write to cell without any verification. PARAMETERS: filepath: Path to Excel file sheet_name: Name of worksheet to write to data: List of lists containing data to write to the worksheet, sublists are assumed to be rows start_cell: Cell to start writing to, default is "A1" |
| `excel create-workbook` | `{filepath: str}` | Create new Excel workbook. |
| `excel create-worksheet` | `{filepath: str, sheet_name: str}` | Create new worksheet in workbook. |
| `excel create-chart` | `{filepath: str, sheet_name: str, data_range: str, chart_type: str, target_cell: str, title?: str = "", x_axis?: str = "", y_axis?: str = ""}` | Create chart in worksheet. |
| `excel create-pivot-table` | `{filepath: str, sheet_name: str, data_range: str, rows: list[str], values: list[str], columns?: list[str] = null, agg_func?: str = "mean"}` | Create pivot table in worksheet. |
| `excel create-table` | `{filepath: str, sheet_name: str, data_range: str, table_name?: str = null, table_style?: str = "TableStyleMedium9"}` | Creates a native Excel table from a specified range of data. |
| `excel copy-worksheet` | `{filepath: str, source_sheet: str, target_sheet: str}` | Copy worksheet within workbook. |
| `excel delete-worksheet` | `{filepath: str, sheet_name: str}` | Delete worksheet from workbook. |
| `excel rename-worksheet` | `{filepath: str, old_name: str, new_name: str}` | Rename worksheet in workbook. |
| `excel get-workbook-metadata` | `{filepath: str, include_ranges?: bool = false}` | Get metadata about workbook including sheets, ranges, etc. |
| `excel merge-cells` | `{filepath: str, sheet_name: str, start_cell: str, end_cell: str}` | Merge a range of cells. |
| `excel unmerge-cells` | `{filepath: str, sheet_name: str, start_cell: str, end_cell: str}` | Unmerge a range of cells. |
| `excel copy-range` | `{filepath: str, sheet_name: str, source_start: str, source_end: str, target_start: str, target_sheet?: str = null}` | Copy a range of cells to another location. |
| `excel delete-range` | `{filepath: str, sheet_name: str, start_cell: str, end_cell: str, shift_direction?: str = "up"}` | Delete a range of cells and shift remaining cells. |
| `excel validate-excel-range` | `{filepath: str, sheet_name: str, start_cell: str, end_cell?: str = null}` | Validate if a range exists and is properly formatted. |
| `excel get-data-validation-info` | `{filepath: str, sheet_name: str}` | Get all data validation rules in a worksheet. This tool helps identify which cell ranges have validation rules and what types of validation are applied. Args: filepath: Path to Excel file sheet_name: Name of worksheet Returns: JSON string containing all validation rules in the worksheet |

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

## git

Use `git --help` for Git operations on workspace repositories.

## python3

Execute Python code directly under the agent workspace and return stdout
and stderr. Code can be pasted into a `.py` file and run with `python3`.

Python cannot launch subprocesses or make direct network requests. Run the
documented service commands directly in the shell. Use Python for local
file processing and generating JSON arguments.
