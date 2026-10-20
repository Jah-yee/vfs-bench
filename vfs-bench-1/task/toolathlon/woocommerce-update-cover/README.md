# woocommerce-update-cover

Update product cover images from sales of their variations. The original
WooCommerce MCP and our read-only `/woo` mount and separate `woocommerce` CLI use
the same WordPress, WooCommerce and MySQL service in E2B.

The committed fixture captures the original task's seeder, including its
generated orders, uploaded images and private expected-results file.
Each arm restores this snapshot into a fresh sandbox, then compares hashes
of every product, variation, order, customer and category before the agent
starts. This preserves the original random values and timestamps across
arms. The original grader runs inside that sandbox and checks persisted
featured-image IDs. Cleanup runs after grading or failure.

WooCommerce randomly shuffles `related_ids` on each product read. Only the
validation hash sorts those IDs; the service responses are unchanged.
Related-product membership and every other field are still checked.

The task prompt is copied byte for byte from the pinned Toolathlon commit.
`capture-woocommerce-cover` in `dvc.yaml` records the snapshot and its source
dependencies. The source receipt records original input hashes, service
image digests and snapshot checksums. Expected results are restored outside
the agent workspace. Neither the task prompt nor MCP schemas are changed.

Use the existing [WooCommerce setup](../inventory-sync/README.md). For a
deliberate new capture, the builder is
`uv run python -m task.toolathlon.script.capture_woocommerce woocommerce-update-cover`; it requires
E2B credentials and refuses to overwrite an existing capture.

Check fixture lineage:

```sh
uv run dvc status
```

Model runs, with E2B and model credentials configured:

```sh
uv run python agent/run_agent.py toolathlon/woocommerce-update-cover --tools mcp
uv run python agent/run_agent.py toolathlon/woocommerce-update-cover --tools vfs
```

The live integration passed, including pagination, both mutation surfaces and
read-after-write checks through the mount.

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
