# train-ticket-plan

Converted from the pinned original Toolathlon task. The task text, initial files
and evaluator are preserved; each arm starts with fresh writable state.

Tools: `filesystem`, `rail_12306`, `terminal`, `fetch`.

The original config explicitly requests `12306-mcp@0.3.9`; its dependency tree
is locked. The original grader launches that same server and receives the
run’s launch timestamp. The transport preserves the original language header
and separate session cookies; both tool interfaces pass startup and schema
parity against the live railway service.

VFS exposes `web-search`, `fetch`, `rail-12306`. Use each command’s `--help` for its interface.
The new service CLIs preserve original tool names and JSON schemas and
invoke their handlers directly, without an MCP client.

Setup and source verification:

```sh
uv run python -m server.mcp.setup_travel_video
uv run python -m server.mcp.setup_memory
uv run python -m setup.final_lineage
uv run python setup/lineage.py
uv run dvc status
```

Both arms use the original Node/axios HTTP client behind the shared request cache. Python HTTP forwarding returned error HTML for valid 12306 routes. All four task routes returned identical successful MCP/CLI results under concurrent calls. Bootstrap cookies are fresh, successful ticket responses are shared by exact query, and failed responses are not persisted.

**Upstream grader limitation:** when an answer returns Thursday as `null`, the unchanged grader finds a valid Thursday combination, then accesses `train_no` instead of its parsed `train_number` field. It catches that KeyError and incorrectly accepts the no-ticket claim. The defect is in original `evaluation/main.py`, lines 409–417.

Original task files are read from pinned Git objects.

Evaluator SHA-256: `1476163e1a20f2622e36fa0c60c890b91d55359ca680942b3706d0d0df8cbb5b`.
