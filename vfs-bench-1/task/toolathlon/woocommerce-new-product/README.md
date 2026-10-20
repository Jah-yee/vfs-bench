# woocommerce-new-product

Send reservation notices for upcoming products and discount reminders to customers.

Both arms use the original WooCommerce service in a fresh E2B sandbox.
The `/woo` mount provides live reads; the separate `woocommerce` CLI performs
service writes. The MCP arm runs the pinned original server and dependency tree.
The owned mail service runs in the same sandbox; `/mail` provides read-only
inspection and `emails` invokes the pinned original handlers for operations.

Each arm runs upstream's own preprocess on every run, as upstream does. It
seeds seven products, 40 customers and the original private expected-results
files, with launch dates, sale windows and creation dates set relative to the
seeding time, so the task's windows hold on every run. Missing subscription
metadata stays missing, as upstream specifies; the conversion does not add
subscribers.

The task prompt is copied byte for byte from the pinned Toolathlon source.
The run record hashes the upstream task, seeder and grader files it copied
into the sandbox and lists the service images. The harness runs the original
grader inside the sandbox and deletes the sandbox after the run or a failure.

Use the existing [service setup](../inventory-sync/README.md) and configure `E2B_API_KEY` and model credentials.
Run the arms sequentially because their local service ports are fixed:

```sh
uv run python agent/run_agent.py toolathlon/woocommerce-new-product --tools mcp
uv run python agent/run_agent.py toolathlon/woocommerce-new-product --tools vfs
uv run dvc status
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
the recorded tool implementation and schema hashes before startup.
