# W&B task conversion

`wandb-best-score` and `wandb-shortest-length` use the original Toolathlon
prompts, initial workspaces and graders at `9be8d8fe`. Both arms read a
frozen public capture of `mluo/deepscaler-1.5b`: five runs, 3,319 history rows
and 31 downloadable files. Nothing is derived from the graders.

The VFS arm mounts Mirage's built-in `wandb` resource at `/wandb`. The MCP
arm runs Toolathlon's named `lockon-n/wandb-mcp-server` fork at
`83f6d7fe2ad2e6b6278aef4a792f35dd765fd315`, retaining its dependency versions
in `vendor/wandb-mcp/uv.lock`. The bare package in upstream's launch command
is no longer published on PyPI. Its six tools and their schemas are unchanged.

Each arm starts and closes its own loopback API, using Mirage's pinned mock
at `245bf3f2a96442caf830c098c15248e103624eba`. The benchmark adapter restores
observed pagination, run ordering, metadata and history sampling. Authentication
uses a fixture key; public data capture and benchmark runs need no W&B account.
These two tasks use the existing local shell/Python runtime and need no E2B.

The API supports experiment reads within Mirage's GraphQL schema. Default
history samples, one-step windows and 2,125 selected-history responses are
captured from W&B; full-resolution reads use the complete histories.
Uncaptured downsampling or one-step windows, unsupported filters, Weave,
support-bot calls and report writes are outside
this fixture. A run exercising these gaps is not a faithful MCP comparison.
All MCP divergences are declared in `server/mcp/mcp_servers.py`.

`dvc.yaml` tracks both task prompts and the capture. `capture-wandb` is frozen:
`dvc repro` never silently refreshes the public data. Captures record the
upstream revision, task hashes, capture-script hash and dependency-lock hash.
A refresh publishes only after every phase succeeds and source metadata is
rechecked. The unfrozen `wandb-lineage` stage watches the task inputs, API
adapter, MCP lock, Mirage runtime and runner without fetching public data.

To deliberately recapture, run
`uv run python task/toolathlon/script/capture_wandb.py`, review the change,
then run `uv run dvc commit capture-wandb -f`,
`uv run dvc repro wandb-lineage` and `uv run dvc status`.

New run dumps record source fingerprints before execution and the grader's
exit code afterward. A failed grade makes the runner exit unsuccessfully,
even when the agent loop completed. Older dumps are not backfilled.

After the repository setup, verify with:

```bash
uv run python tests/parity.py wandb-best-score wandb-shortest-length
uv run python tests/wandb_tasks.py
uv run python tests/toolathlon_fidelity.py
uv run python tests/wandb_capture.py
uv run python tests/run_outcome.py
uv run python tests/lineage.py
uv run dvc status
```

To verify the frozen capture against the live service rather than against
itself, run `uv run python task/toolathlon/script/check_wandb.py`. It
re-reads every captured observation from the public API -- project and run
metadata, the 3,319 history rows, the default and explicit samples, the 195
one-step windows and the 2,125 selected-key samples -- and prints each
difference; it writes nothing, so a refresh stays a deliberate
`capture_wandb.py` run.

The two views the arms get are both the service's own. The VFS mount is the
complete history, which is what `scan_history` returns; the MCP default is
the 500-point sample W&B itself computed. They differ only for `2h1sn79d`,
the one run with more than 500 rows, and its captured samples are irregular:
step gaps of 1 to 6, and a five-point sample of `val/test_score/` at steps
470, 970, 1180, 1400 and 1410. No rule reproduces that, so a request for an
uncaptured downsampling of that run is refused rather than approximated;
the 425 selected-key specs captured per run cover the task metrics at every
sample count from 1 to 20 and at 50, 100, 200, 500 and 1000.

The third original W&B task, `experiments-recordings`, also needs the original
Notion page `mcp_experiments_recordings`. Its initial page state is absent from
the upstream checkout, so that task remains unconverted.

The Kubernetes integration added E2B dependencies to the root lock. A new
capture records that lock: run histories, sampled histories and downloaded
files are unchanged. W&B now reports its internal runtime summary as a dotted
key and absent system metrics as null; both arms use the newly captured
metadata.
