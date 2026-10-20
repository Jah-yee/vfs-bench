# W&B best score

Find the experiment and step with the highest validation score in
`mluo/deepscaler-1.5b`, then write `best_experiment.csv`.

```bash
uv run python agent/run_agent.py toolathlon/wandb-best-score --tools vfs
uv run python agent/run_agent.py toolathlon/wandb-best-score --tools mcp
```

The 16 parity cases pass. See [shared fixture lineage and API
boundaries](../shared/WANDB.md).
