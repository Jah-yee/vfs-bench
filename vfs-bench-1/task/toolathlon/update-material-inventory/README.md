# update-material-inventory

Apply WooCommerce orders to the BOM and material-inventory Sheets.

Both arms restore the same captured original seed in fresh E2B sandboxes.
The WooCommerce mount supplies live reads; the separate CLI supplies writes.
The MCP server and its dependency tree are pinned to the upstream baseline.

The capture contains 3 original products, 3 orders, both source tabs, generated SKU mappings and private expected results.

`capture-update-material-inventory` in `dvc.yaml` links the fixture to the original task,
seeder/grader files, service images and capture code. `source.json` records
upstream file hashes and artifact checksums. The harness validates restored
API state and runs the original grader in the sandbox before cleanup.

Source/artifact checks and DVC pass; no test files were added.

Use the existing [service setup](../inventory-sync/README.md) with
`E2B_API_KEY`. Run the arms sequentially because the native service ports
are fixed:

```sh
uv run python agent/run_agent.py toolathlon/update-material-inventory --tools mcp
uv run python agent/run_agent.py toolathlon/update-material-inventory --tools vfs
uv run dvc status
```

The Sheets source XLSX has its own frozen capture stage and receipt. The API fixture preserves values, cell formats and date rendering for both surfaces and the grader.

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

## Original Google tool CLI — 2026-09-13

The current interface is `google-sheet <original-tool-name>` with one JSON argument object. It invokes the pinned original MCP handlers and preserves their schemas, defaults and responses. The broad `gws` registration has been removed. The Sheets CLI has exactly 20 commands, including the original folder tools.

Live read/write and schema parity checks passed. `tests/parity.py` checks this CLI's commands against the server's tools on every run.
