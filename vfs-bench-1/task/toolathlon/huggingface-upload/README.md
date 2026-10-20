# Hugging Face upload

Select the workspace checkpoint with the highest `eval_accuracy`, upload
its folder as `MyAwesomeModel-TestRepo`, and update only the 15 benchmark
scores in the supplied README, keeping three decimal places.

The original prompt is in [shared/task.md](shared/task.md). The VFS
[workspace](vfs/workspace.yaml) mounts the agent's files at `/work` and
uses the separate `hf` CLI to upload to the fixture Hub. The Hub is an
output destination rather than a mounted input repository. The original
grader expects `MyAwesomeModel-TestRepo` under the authenticated user's
namespace.

After the usual repository setup, run each surface through the existing
runner, which seeds and grades the task:

```sh
uv run python agent/run_agent.py toolathlon/huggingface-upload --tools mcp
uv run python agent/run_agent.py toolathlon/huggingface-upload --tools vfs
```

The repository's `ask@huggingface-upload` DVC stage links the prompt to
the pinned original task.
