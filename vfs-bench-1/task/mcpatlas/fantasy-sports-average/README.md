# Fantasy sports average

> I was reviewing my sports data on my computer, and I am sure that the
> average score of the athletes is less than 80, while my father believes it
> is over 100. Can you help me determine who is correct?

Eight CSVs sit in `/data` — beside the `repos/` directory Atlas's image also
puts there — and nothing says which one is "sports data". Find it, average
its score column, and say who was right.

## The surface

| arm | tools | tool-schema bytes |
|---|---:|---:|
| mirage VFS | **1** | one shell over the mounts |
| MCP-Atlas | **14** | **7,374** |

| server | exposes | task enables | bytes |
|---|---:|---:|---:|
| filesystem | 14 | 10 | 6,115 |
| mcp-code-executor | 9 | 4 | 1,259 |

Counted by booting both servers and summing `len(json.dumps({name,
description, inputSchema}))` over the tools that survive the filter — the
three fields that become an OpenAI tool definition. Nine of the twenty-three
tools the two servers expose are never advertised, because Atlas's row does
not list them.

These numbers predate pinning the filesystem server's
tree to the image's. Its SDK had resolved to 1.30.0 over zod 3, where the
image has 1.29.0 over zod 4, and that adds `"additionalProperties": false` to
nine of the ten schemas this task enables -- 279 bytes the model was sent and
Atlas never sent it. The MCP arm here is that much smaller now.

## Both arms reach the same bytes

`tests/parity.json`, three cases, all agreeing: the same nine entries listed
under `/data`, the same header row, the same file size. The filesystem server
reads the image's own `/data` and mirage's `/data` is a copy of it taken out
of the same image, so this compares two clients over the same bytes at the
same path.

    uv run python tests/parity.py fantasy-sports-average

## The fixture reproduces Atlas's ground truth exactly

Atlas's `/data` is not committed here. `script/seed_task.py` copies it out of
the pinned image into `state/mcpatlas/image-<id>/data`, so the image digest is
the whole of its lineage and there is no second copy that could drift from it.
`shared/task.md` and `shared/atlas.json` are committed, because the Hub is not
a checkout, and `dvc.yaml` traces them to one row of `ScaleAI/MCP-Atlas` at a
pinned revision. The graded claim is that the mean is `101.05882352941177`,
and the copied file returns exactly that:

```
$ python3 -c "
import csv, statistics
rows = list(csv.DictReader(open('/data/fantasy sports.csv')))
print(len(rows), statistics.fmean(float(r['Points_Scored']) for r in rows))"
51 101.05882352941177
```

Run on the mirage arm, through the shell tool, on pyodide. Nothing is
captured and nothing is invented; there is no fake in this task at all,
because Atlas's fixture for it is a file rather than a service.

## Two things the port turned up in mirage

**`awk` cannot do arithmetic in `print`.** Field printing works; `END {print
s/n}` answers `awk: unsupported construct`. Confirmed on both hosts, so it is
the CLI and not the runtime. `SKILL.md` warned about it; the warning has since
been cut.

**The Python runtime depends on which host, and only one of them is the
arm.** On mirage's Python host, `monty` has no `csv` and no `statistics`;
`wasi` needs a CPython build that is not checked in; `sandlock` is Linux
only; `local` has the stdlib but cannot see the mounts. None of that reaches
the arm, because `--tools vfs` builds on the TypeScript host and gets
pyodide, which is real CPython with a complete standard library. Worth
writing down anyway: it was nearly recorded as a mirage gap on the strength
of the wrong host.

## What is upstream's and what is ours

The tool surface is upstream's, exactly. `shared/atlas.json` holds the dataset
row verbatim — the `TASK` id, the fourteen `ENABLED_TOOLS`, the two
`GTFA_CLAIMS` — and the arm is built from that list rather than from a
restatement of it. Both servers run in Atlas's own image, started as its app
starts them, and their tool names keep Atlas's spelling:
`mcp-code-executor_execute_code`, hyphens intact, which is fastmcp's prefixing
and not Toolathlon's underscore rewrite.

Each of these is a decision rather than a detail:

**The grading is upstream's own.** Atlas scores each claim with an LLM judge
-- fulfilled, partly or not, worth 1, 0.5 and 0 -- and reports the share of
tasks whose coverage reaches 0.75. `script/grade_task.py` runs that scorer,
upstream's `score_claims.py` with its default judge, and passes a run at
0.75. Upstream's first claim here, *the data is in the file
`fantasy sports.csv`*, is an intermediate fact a good answer to the question
asked need not state, and an answer that says "51 athletes, 101.06, your
father is correct" and stops scores 0.5 and fails.

**The harness is upstream's too.** Toolathlon is built on `openai-agents` —
it pins `openai-agents==0.0.15`, which is why this repo carries a second
virtualenv — so the agents runner *is* its harness shape. Atlas has no
framework at all: a TypeScript service, `services/agent-harness`, whose
hand-written `for` loop asks the model over Chat Completions and reaches every
tool through one HTTP app, `services/agent-environment`.
`agent/atlas/` runs both as they are — the MCP arm's app serving the
task's servers, the mirage arm's serving the shell — so **both arms always get
the same loop**, which is the only way a draw comparing surfaces stays a draw
comparing surfaces.

Three settings come off upstream with it. Atlas's request is `{model,
messages, tools}` and nothing else (`litellm-strategy.ts:51`), so
`parallel_tool_calls` is omitted and the provider default stands, where
Toolathlon's own config defaults it to False (`agent_config.py:11`); its turn
cap is 256 (`agent-eval.ts:19`) against Toolathlon's 60; and its tool
definitions carry `strict: false` with the input schema passed through
(`agent-eval.ts:312`). Forcing one tool call per request would cost the arm
with fourteen tools far more than the arm with one, and that is not a
difference in surface.

**The MCP arm gets no system prompt**, because Atlas sends none —
`litellm-strategy.ts:137` adds an empty one for gpt-5 and nothing otherwise.
The mirage arm still needs `VFS.md` and `SKILL.md` to describe mounts and
CLIs that do not otherwise exist. So the asymmetry between the two arms'
prompts is wider here than on any Toolathlon task, where both sides get a
document. That is upstream's shape, not a choice made here, but it is the
first thing to question if a draw looks lopsided.

**The fixture is upstream's image.** Atlas bakes `/data` into its sandbox
image and scopes the filesystem server to it. The MCP arm's servers read that
`/data` in the run's container of the same image, and mirage mounts a copy
taken out of it at `/data`, so both arms are told the same path as well as
handed the same bytes.

## Running it

    uv run python server/mcp/setup_mcpatlas.py            # once
    uv run python agent/run_agent.py mcpatlas/fantasy-sports-average --tools vfs
    uv run python agent/run_agent.py mcpatlas/fantasy-sports-average --tools mcp

Both run on upstream's harness and sandbox app, because that is what this
dataset declares; the run id carries the loop.
`uv run python setup/setup.py` installs the harness, and `setup_mcpatlas.py`
builds the image.

The mirage arm needs mirage's TypeScript host built, and its `engines.node` is
`^22.22.2 || ^24.15.0 || >=26.0.0` — Node 24.12 refuses the `pnpm build` with
`ERR_PNPM_VERIFY_DEPS_BEFORE_RUN`, which reads like a dependency problem and
is a version one.

There is no stack to bring up. This task's fixture is one directory, and its
seeder materialises it out of the pinned checkout rather than resetting a
service — each run gets its own workspace, so there is no previous arm's
answer to wipe.
