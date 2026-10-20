---
name: workspace-commands
description: Use when running commands in this workspace - which commands exist, what they can do, and what the interpreter supports.
---

# Available commands

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip

with pipes, `>` redirection, `$(...)` substitution, `for` loops and `'...'`
quoting.

## python3

Real CPython, sandboxed: no host filesystem, no network, no `subprocess`.
`open()` and `pathlib` reach the mounts by absolute path, and the standard
library is complete, `zlib` and `zipfile` included.

### Document libraries

`/opt/wheels` holds python-pptx (`pptx`) and openpyxl, already on
`sys.path` — no install step and no path setup, just import:

    import pptx
    import openpyxl

## cook

Look up Chinese home-cooking recipes with `cook`. Each verb prints one JSON
document, and every dish name and ingredient in them is Chinese.

    cook all_recipes
    cook categories
    cook recipes_by_category  --category
    cook recipe               --query

**all_recipes** — every dish in the corpus, as a `name` and a
`description`. Large; pipe it rather than reading it whole.

**categories** — the category names `recipes_by_category` accepts.

**recipes_by_category** — one category's dishes, each with `id`, `name`,
`description` and an `ingredients` list of `name` and `text_quantity`. No
cooking steps.

**recipe** — one dish in full: ingredients with quantities, and the steps.
`--query` takes an `id` or a dish name, and falls back to a substring match
on the name. A query that matches nothing exactly prints an object with
`possibleMatches` instead of a recipe, so check which shape you got.

Run `cook <verb> --help` for details.

Run `<command> --help` for full usage.
