# woocommerce-new-welcome

Sync first-order customers to BigQuery and send welcome emails.

Each arm runs upstream's own preprocess in a fresh E2B sandbox on every run,
as upstream does. The WooCommerce mount supplies live reads; the separate CLI
supplies writes. The MCP server and its dependency tree are pinned to the
upstream baseline.

The preprocess seeds 12 orders, 50 CRM rows with their native schema, the welcome template and an empty mailbox. WooCommerce stamps the orders when they are seeded, so the task's past-7-days window holds on every run. BigQuery runs in the same owned E2B instance, behind the stack's `server/bq/proxy.py`, and so do the Cloud Storage fake and the Cloud Logging fixture API that its google-cloud server also reaches.

The run record hashes the upstream task, seeder and grader files it copied
into the sandbox and lists the service images. The harness runs the original
grader in the sandbox before cleanup.

Use the existing [service setup](../inventory-sync/README.md) with
`E2B_API_KEY`. Run the arms sequentially because the native service ports
are fixed:

```sh
uv run python agent/run_agent.py toolathlon/woocommerce-new-welcome --tools mcp
uv run python agent/run_agent.py toolathlon/woocommerce-new-welcome --tools vfs
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
