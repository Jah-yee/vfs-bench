# Verl dataset

Both arms now search 485 captured public Hub candidates with recorded download counts; VFS no longer receives an answer-specific mount. The winning dataset bytes remain the pinned upstream ground truth. Search/fetch use the existing research transport and require SERPER_API_KEY.

The capture preserves candidate metadata for ranking; only the winning repository's dataset file is available in the fixture. It does not mirror all candidate repositories or establish their historical download counts.

Find the most downloaded DeepScaleR dataset on Hugging Face and convert it
to `verl_deepscaler.parquet` using the workspace's `format.json`.

The original prompt is in [shared/task.md](shared/task.md). The VFS
[workspace](vfs/workspace.yaml) provides Hub search and file download commands without naming the answer
repository in the prompt.
Python runs in Pyodide with `pyarrow` available for Parquet output, and
writes the answer to `/work`.

After the usual repository setup, run each surface through the existing
runner, which seeds and grades the task:

```sh
uv run python agent/run_agent.py toolathlon/verl-dataset --tools mcp
uv run python agent/run_agent.py toolathlon/verl-dataset --tools vfs
```

The repository's `ask@verl-dataset` DVC stage links the prompt to the
pinned original task. Its captured Hub candidates have a `verl-hub-search` DVC stage.

## The Dataset Viewer answers are the live server's — 2026-09-19

mirage's Hub fake refuses `hub_repo_details`' `dataset_structure` and
`dataset_preview`. `shared/hub-viewer/` holds 24 responses captured from
`huggingface.co/mcp` (server 0.4.20) on 2026-09-19 for
`agentica-org/DeepScaleR-Preview-Dataset`: its structure, alone and beside
the other operations, and the preview pages an agent reaches for. The
source dataset is seeded from upstream's own copy of its one file rather
than a pinned Hub revision, so the receipt records the live revision the
answers describe. `server/fakes/hub_viewer.py` answers those requests from
the capture in front of the fake, for the tool on the MCP arm and the
`huggingface` CLI on the mirage arm alike, and the `dataset_structure`
parity case reads the same captured answer through both.
