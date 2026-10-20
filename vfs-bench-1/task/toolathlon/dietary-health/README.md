# Dietary health

Read a day's three dishes, look each one up in a 322-recipe corpus to find
what it is made of and how much, price every ingredient against an 86-row
nutrition spreadsheet, work out the day's carbohydrate and protein targets
from a height, a weight and a page of training guidance, and write the
verdict into `analysis.md` in an exactly specified format.

## Both arms read the same recipes

The corpus comes from `howtocook-mcp` 0.2.2, vendored and pinned by
[`server/mcp/setup_howtocook.py`](../../../server/mcp/setup_howtocook.py) — see
[cooking-guidance](../cooking-guidance/README.md) for why the pin matters and
how the two surfaces are held to the same bytes.
The `howtocook` CLI is the CLI arm of it: the pinned server's own handlers,
served through [`cli/toolathlon/travel-video.mjs`](../../../cli/toolathlon/travel-video.mjs), so its
documents are the server's byte for byte.

This task runs on pyodide because the nutrition table is an xlsx and xlsx is
a zip: pyodide is the only runtime here with `zlib`.

## What the task actually asks

The hard part is not arithmetic, it is reading amounts out of prose. One
portion of 西红柿炒鸡蛋 is `1.5 个 * 份数，向上取整` of egg — two eggs, not
one and a half — and its oil is `4ml * 鸡蛋/个`, so eight millilitres because
of that rounding. A 斤 of fish is 500g. Two 朵 of shiitake, one 根 of spring
onion and two 个 of chilli are all counts, and the spreadsheet's 备注 column
is where each becomes grams: `1朵约15g`, `1根约10g`, `1个约3g`. Three
ingredients are spelled differently on the two sides — the recipe writes 糖
where the table writes 白砂糖, 姜末 where it writes 姜, and the table glosses
瘦肉 as 瘦肉（猪肉）.

Three amounts are ranges (`盐 = 1.5-2g`, `糖 = 0-2g`, `葱花 = 0-10g`), and
`format.md` says to average them — which the ground truth does by totalling
the low ends and the high ends separately and halving the sum.

The target range is the other half. A male in the initial fat-loss phase gets
2.5–3 g/kg of carbohydrate and 1.5 g/kg of protein; a BMI over 28 replaces
those with 2.4–2.7 and 1.2; and a rest day takes another 0.5 off the
carbohydrate. At 65kg that is 123.5–143g and 78g. The meals supply about
131g and 151g, so carbohydrate meets the target and protein is nearly double
it.
