# inventory-sync

Original WordPress, WooCommerce and MySQL services in E2B. The upstream
seeder supplies the six SQLite warehouses and store products. `/woo` is a
read-only REST mount; the separate `woocommerce` CLI updates the same service.
The original stock validator runs inside the owning sandbox.

Each measured arm owns a fresh sandbox through grading, then deletes it.
Prompts and fixtures come from the pinned Toolathlon checkout. DVC tracks
the captured artifacts and dependency sources; run records include image
digests and source hashes. No task-specific canned SQL responses are used.

After the usual repository setup, export `E2B_API_KEY` and install:

```sh
uv run python -m server.mcp.setup_kubernetes
uv run python -m server.mcp.setup_commerce_canvas
uv run python server/kubernetes_template.py
```

Live integration (requires E2B credentials):

```sh
uv run python tests/business_tasks.py BusinessTasks.test_inventory_sync
```

## Current CLI and lineage

`woocommerce` now invokes the pinned original tool handlers directly, without an
MCP client. Commands drop the `woo_` prefix and retain the original
schemas, pagination, defaults and response text. Use `woocommerce --help` and
`woocommerce <command> --help`. The filesystem mount still enumerates complete
REST collections independently of CLI pagination. Python is for processing
files and data; invoke service commands directly in the shell.

The `service-mcp-tools` DVC stage installs the original dependency locks and
derives `vendor/woocommerce-mcp/tools.json` and `source.json`. Both arms verify
the recorded tool implementation and schema hashes before startup. Existing
fixture captures retain their DVC source links and bytes.
