# Cooking guidance

Read a list of ingredients on hand, pick three dishes out of a 322-recipe
Chinese home-cooking corpus that use as many of them as possible, write the
dish names into `cuisine.json`, and write everything still missing into a
`shopping.csv`.

## The corpus is the fixture, and it is pinned

Upstream runs the server as `npx -y howtocook-mcp`, which resolves whatever
npm published that day. That matters more here than the usual
reproducibility complaint, because both tasks using this server are graded
against a static ground truth derived from the recipe corpus: a corpus that
moves makes them unpassable rather than merely irreproducible.

[`server/mcp/setup_howtocook.py`](../../../server/mcp/setup_howtocook.py) pins 0.2.2
into `vendor/howtocook-mcp/`. That release reads `all_recipes.json` off disk
and never touches the network; earlier ones fetched `weilei.site` first and
fell back to the bundle only when offline, so a graded run depended on
whether the network was up. Its corpus is byte-identical (sha256
`d4330dfe…207bdd`) to the copy the ground truth was built from — 290 of the
293 dishes under `groundtruth_workspace/dishes/` are in it with matching
ingredient lists, and the three absentees are `示例菜` ("example dish"),
`糖色`, and a duplicate.

## Both arms read the same file

The `howtocook` CLI runs the pinned server's own handlers through
[`cli/toolathlon/travel-video.mjs`](../../../cli/toolathlon/travel-video.mjs), so it reads that
same `all_recipes.json` rather than a converted copy of it. The corpus is
nearly path-shaped and would have extracted cleanly into
`dishes/<category>/<name>.md`, which is what the other tasks in this repo do
with a tree-shaped fixture — but extracting it would have put a
transformation between two surfaces whose whole claim is that they read the
same bytes. One file, no conversion, nothing to keep in step.

The documents match upstream byte for byte, including `JSON.stringify(x,
null, 2)`'s two-space indent and its unescaped UTF-8 — on a corpus that is
entirely CJK, `ensure_ascii` alone would have been the difference between
the two arms reading the same document and one of them reading `\u`-escapes.
Verified across eight cases: `getAllRecipes`, two categories, and the five
branches of `getRecipeById` (exact id, exact name, unique substring,
multi-match, no match).

Three of upstream's five tools are on the CLI. `recommendMeals` and
`whatToEat` are missing because they are `Math.random()` recommenders: they
answer differently on every call, no evaluator can pin them, and neither task
mounting this server has a ground truth that could depend on one. `cook
categories` is there and upstream has no tool for it, because upstream puts
the category list in `getRecipesByCategory`'s schema — an MCP client reads it
for free before calling anything, and a CLI has to be asked.

## How the grader works

It does not ask the server what a dish needs. `evaluation/check_local.py`
parses `groundtruth_workspace/dishes/<name>.md` itself with its own
`RecipeQuantityExtractor`, and only falls back to the MCP server when a dish
is missing from that tree. So a shopping list is built from one parse of the
recipes and graded against another, and an ingredient the two spell
differently is a real failure mode rather than a hypothetical one.

Two thresholds: the three dishes together must use at least 50% of the
ingredients in stock, and the shopping list must cover at least 90% of what
is short — with anything held *but insufficient* an outright failure if
absent, since that is the case an agent is most likely to overlook.

Matching is fuzzy on both sides. Substring either way counts, so `瘦猪肉片`
in stock covers a recipe asking for `猪肉末`, and the four meats match on the
meat alone. Quantities aggregate across stock entries before being compared,
so 150g of one cut plus 100g of another meets a 250g requirement.
