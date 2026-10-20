# Offline trace analysis

`analyze_trace.py` reads saved Agents-loop dumps. It never executes their
commands, calls a model, changes prompts or alters fixtures.

From the repository root:

```bash
uv run python agent/analyze_trace.py \
  dumps/<vfs_run_id>.json \
  dumps/<mcp_run_id>.json \
  > /tmp/trace-analysis.json
```

Pass explicit dump paths to avoid mixing superseded
attempts with selected results. The JSON records each trace's SHA-256, the
analyzer's SHA-256, saved settings, source fingerprints, raw grader record and
usage. Output can contain short command excerpts; review it before
publication.

## Measurements

- **Response batching:** group function calls by recorded provider response ID.
  Report the batch sizes, fraction of identified calls in multi-call responses,
  and calls missing response IDs. This measures decisions issued together,
  not observed execution overlap or the fraction of parallelizable work used.
- **Returned data:** UTF-8 byte sizes of model-visible shell outputs, falling
  back to recorded output in older traces; also report serialized tool-output
  sizes for both arms. These overlap and must not be added. They are neither
  token counts nor backend bytes read. Structured non-string outputs use a
  deterministic JSON representation for measurement.
- **Exact repeats:** identical tool name/JSON argument pairs, exact shell
  command strings, and identical nonempty serialized tool outputs. Report
  occurrence indices. Repetition does not prove waste: state can change and
  verification can be justified. Different commands reading the same file
  are not recognized as repeats.
- **Diagnostic candidates:** selected error strings and malformed-glob output
  patterns, linked to zero-based shell-log indices. These are review leads,
  not certified failures: output can quote an error, and quiet failures can
  escape detection. Multiple markers can describe one operation.

The script intentionally does not infer shell ASTs, resources accessed inside
scripts, useful versus unnecessary work, completion time, native thinking
settings, or actual concurrency. Historical traces lack the observations
needed to measure these reliably. Missing measurements remain unknown.

## Interpretation for a study

Compare successful outcomes and failed attempts separately, with task-level
results rather than only pooled tokens. A completed loop is not a passed task;
nonzero grader status can mean either an incorrect result or a grader exception.
Check revisions, output caps, task dates, credentials/fixtures and native
reasoning settings before calling a model comparison controlled. Cached input
is already included in the dump's input count and must not be added again.
`reasoning_tokens` is included in `output_tokens`; an absent field means
the reasoning share was not recorded.

Do not rank agents by batch rate or command count alone. More batching may
coexist with more overall work; a single script can perform many operations.
A useful next measurement requires resource read/write events, content hashes,
exit codes and timestamps, plus explicit definitions of independent operations
and necessary verification. Semantic redundancy needs annotation or validated
resource-level analysis, not keyword counts.

For related work, [tau-bench](https://arxiv.org/abs/2406.12045) evaluates final
state correctness and repeated-run reliability (`pass^k`: success on all k
independent trials). It does not establish these shell-efficiency metrics.
Use repeated matched trials to test whether fewer steps preserve reliability.
