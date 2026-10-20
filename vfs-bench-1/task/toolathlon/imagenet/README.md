# ImageNet survey table

From several image-generation papers in the workspace, collect each model's
ImageNet 256 results into a LaTeX table in `survey.tex`: model name (the
lowest-FID variant where a paper reports several), method category (VAE, GAN,
Diffusion, Flow-based or AR), parameter count, FID-50K and Inception Score,
sorted by descending FID.

```bash
uv run python agent/run_agent.py toolathlon/imagenet --tools vfs
uv run python agent/run_agent.py toolathlon/imagenet --tools mcp
```
