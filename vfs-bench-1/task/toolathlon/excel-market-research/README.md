# Excel market research

From `Market_Data.xlsx`, compute each segment's year-over-year growth rate for
2015–2024 using the segment/source mapping in the `Methodology` sheet, rounded
to one decimal place, and write `segment_growth_rates.xlsx` with `Year` first
and the segment columns in the order `Methodology` lists them.

The brief says "growth rate … rounded to one decimal place", which reads
naturally as `4.3`, and the ground truth wants `0.043` — one decimal place
would make that `0.0`. This is a task-specification ambiguity that the tool
surface does not touch.
