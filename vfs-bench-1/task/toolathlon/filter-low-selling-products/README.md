# filter-low-selling-products

Find slow-selling products, move them into Outlet/Clearance and email the original subscribers.

Both arms use the original WooCommerce service in a fresh E2B sandbox.
The `/woo` mount provides live reads; the separate `woocommerce` CLI performs
service writes. The MCP arm runs the pinned original server and dependency tree.
The owned mail service runs in the same sandbox; `/mail` provides read-only
inspection and `emails` invokes the pinned original handlers for operations.

The snapshot contains 398 products, the original subscriber list and templates, and the private grader files. It preserves product metadata and original timestamps. WooCommerce randomly samples `related_ids`; only that field is excluded from API comparison hashes. Model responses are unchanged.

The task prompt is copied byte for byte from the pinned Toolathlon source.
DVC stage `capture-filter-low-selling-products` records the capture and its source dependencies.
The source receipt records upstream input hashes, pinned service images and
artifact checksums. Before execution, the harness restores the snapshot and
compares API state hashes. It runs the original grader inside the sandbox and
deletes the sandbox after the run or a failure.

Use the existing [service setup](../inventory-sync/README.md) and configure `E2B_API_KEY` and model credentials.
Run the arms sequentially because their local service ports are fixed:

```sh
uv run python agent/run_agent.py toolathlon/filter-low-selling-products --tools mcp
uv run python agent/run_agent.py toolathlon/filter-low-selling-products --tools vfs
uv run dvc status
```

For a deliberate fresh capture, use
`uv run python -m task.toolathlon.script.capture_woocommerce filter-low-selling-products`.
The producer refuses to overwrite an existing capture.

Dates are not rebased. These tasks use current-date selection rules, so recapture before a date boundary changes which products qualify; DVC hashes alone cannot detect an expired task time window.

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
