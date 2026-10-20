# k8s-deployment-cleanup

Original Toolathlon task: identify outdated development deployments, stop
them, and notify the cluster administrator named in the supplied PDF.

Each arm gets a fresh Kind cluster in E2B. The original setup script,
manifest, image loader, initial PDF and grader come from the pinned
Toolathlon checkout. Mail uses the existing local GreenMail fixture.

The VFS mount reads the Kubernetes API directly. The separate `kubectl` CLI
and the unchanged upstream MCP server use the same credential-free kubeconfig.
A harness-owned `kubectl proxy` keeps cluster credentials outside the agent
workspace and forwards requests through the TLS tunnel to E2B. Its private
config is removed on exit. The cluster stays alive through grading and is
deleted when the run exits. The existing
Toolathlon instance config is copied to E2B. Its kubeconfig backup is scoped
to the run and any previous backup is restored afterward.

## Setup and runs

After the repository's usual dependency and stack setup, export
`E2B_API_KEY`, then install the pinned client/MCP dependencies and build a
reusable template in your E2B account:

```sh
uv run python server/mcp/setup_kubernetes.py
uv run python server/kubernetes_template.py
uv run python agent/run_agent.py toolathlon/k8s-deployment-cleanup --tools vfs
uv run python agent/run_agent.py toolathlon/k8s-deployment-cleanup --tools mcp
```

Template builds and sandbox runs use the supplied E2B account. The local
receipt is `state/kubernetes-template.json`. Sandboxes have a 60-minute
maximum lifetime and are deleted in `finally`, including setup failures.

```sh
uv run python tests/kubernetes_lineage.py
uv run python tests/kubernetes_proxy.py
node tests/kubernetes_mount.mjs
uv run python tests/kubernetes_tasks.py
```

The live test requires the local mail stack and E2B credentials. It
compares the real surfaces, checks concurrent MCP reads, stale reads after
writes and piped input, and runs the original grader after each arm's cleanup.

## Lineage and limits

DVC tracks the original prompt, email config, upstream MCP dependency
closure and conversion code. The Kubernetes MCP fork and every runtime npm
dependency are copied from Toolathlon's package lock. Docker and Kind match
its Dockerfile; `kubectl` is pinned to Kind's Kubernetes version because
upstream downloads a moving stable client. Release checksums are recorded
and verified before execution.

Run records include the template/build IDs, source hashes, binary checksums,
container image IDs/digests, instance-config hash and sandbox ID. Upstream computes release dates
relative to seeding time and uses an nginx image tag; these are not frozen
API response bytes. Compare semantic fixture content between fresh arms,
and inspect recorded image digests when comparing runs.

The mount is read-only and targets built-in resources. API discovery is
cached per workspace; dynamic CRD installation is not covered. The native
CLI reads `/work` files or piped stdin; it does not expose arbitrary VFS
mounts as host files. This task does not require FUSE or SSH.
