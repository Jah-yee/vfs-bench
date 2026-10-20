# k8s-safety-audit

Original cluster setup and grader, plus a frozen export of the original
audit Sheet. `/k8s` and `/gd` provide reads; `kubectl` and `gws` perform
operations on the same cluster and workbook.

Each measured arm owns a fresh sandbox through grading, then deletes it.
Prompts and fixtures come from the pinned Toolathlon checkout. DVC tracks
the captured artifacts and dependency sources; run records include image
digests and source hashes. No task-specific canned SQL responses are used.

After the usual repository setup, export `E2B_API_KEY` and install:

```sh
uv run python -m server.mcp.setup_kubernetes
uv run python server/kubernetes_template.py
```

The existing Google Workspace fixture must also be running. The original
Sheet values use that fixture; a per-run adapter preserves cell fonts,
alignment and borders, with format updates and copies exposed to both
surfaces. The original grader reads the same endpoint. Other Sheets
features retain the existing fixture’s limits.

Live integration (requires E2B credentials):

```sh
uv run python tests/kubernetes_extended.py KubernetesExtended.test_safety_audit
```

## Original Google tool CLI — 2026-09-13

The current interface is `google-sheet <original-tool-name>` with one JSON argument object. It invokes the pinned original MCP handlers and preserves their schemas, defaults and responses. The broad `gws` registration has been removed. The Sheets CLI has exactly 20 commands, including the original folder tools.

Live read/write and schema parity checks passed. `tests/parity.py` checks this CLI's commands against the server's tools on every run.
