# W&B shortest length

Choose the experiment that produces the shortest responses, then write its
entropy loss, clipping ratio and mean response length every 100 steps to
`shortest_length_experiment.csv`.

```bash
uv run python agent/run_agent.py toolathlon/wandb-shortest-length --tools vfs
uv run python agent/run_agent.py toolathlon/wandb-shortest-length --tools mcp
```

The 16 parity cases pass, and results computed from each surface pass the
unchanged upstream grader. See [shared fixture lineage and API
boundaries](../shared/WANDB.md).
