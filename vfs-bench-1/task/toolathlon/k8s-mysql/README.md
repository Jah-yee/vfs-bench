# k8s-mysql

Original MySQL 8.4 cluster and F1 CSV/schema fixtures in E2B. The original
MCP servers and native `kubectl` run through SSH; Python uses the native
E2B runtime and the original locked Python environment. `/work` shares an
S3 prefix through Mirage and remote FUSE. `/k8s` reads live objects, while
`mysql` is Oracle's 8.4.11 client, the task pod's own version, run through
SSH beside the port-forward. Only the VFS workspace installs it: upstream's
task image has no `mysql` for the MCP arm's Python to find. This CLI
accepts one statement per request.

Each measured arm owns a fresh sandbox through grading, then deletes it.
Prompts and fixtures come from the pinned Toolathlon checkout. DVC tracks
the captured artifacts and dependency sources; run records include image
digests and source hashes. The original grader runs in that same sandbox,
where it can inspect the real port-forward process and connect to MySQL.
Grader files are uploaded privately after the agent finishes.

The disposable integration preflight uses golden CSVs solely to verify
grader connectivity; these files are never seeded into agent inputs. The
preflight checks include the actual remote port-forward and original
cluster resources.

After the usual repository setup, configure `E2B_API_KEY`, AWS credentials,
`BENCH_S3_BUCKET` and `BENCH_S3_PREFIX` in `.env.development`, then install:

```sh
uv run python -m server.mcp.setup_kubernetes
uv run python server/kubernetes_template.py
```

Run each surface with a fresh fixture:

```sh
uv run python agent/run_agent.py toolathlon/k8s-mysql --tools mcp --model openai/gpt-5.6-luna --reasoning-effort medium
uv run python agent/run_agent.py toolathlon/k8s-mysql --tools vfs --model openai/gpt-5.6-luna --reasoning-effort medium
```

Each run gets its own S3 prefix. Result files are retained there and
copied beside the local run artifacts after grading; the E2B sandbox is
deleted. Python launchers select the locked environment even when the
SDK's login shell resets `PATH`.
