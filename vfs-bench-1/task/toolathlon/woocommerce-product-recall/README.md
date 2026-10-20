# woocommerce-product-recall

Take the recalled model off sale, create the template’s Google Form, email affected customers and save the form report.

The frozen capture contains the original MySQL database, WordPress uploads, workspace templates and private recalled-product/customer metadata. Each arm restores the same capture into a fresh E2B sandbox with an empty Forms collection and mailbox. The original grader runs against the resulting native store, Forms API and mail service.

VFS uses `/woo`, `/mail` and `/work` plus separate `woocommerce`, `emails` and `google-forms`
CLIs. MCP uses the original WooCommerce, email and Forms servers. The email
and Forms CLIs directly invoke the corresponding original handlers, preserving
their tool names, schemas and responses.

`capture-woocommerce-product-recall` in `dvc.yaml` records the fixture dependencies. The
`papers-forms-lineage` stage checks original task text, source receipts,
server locks, artifact hashes and CLI timeouts against upstream.
See [setup and shared validation](../README.md#paper-forms-and-canvas-conversions).

```sh
uv run python agent/run_agent.py toolathlon/woocommerce-product-recall --tools mcp
uv run python agent/run_agent.py toolathlon/woocommerce-product-recall --tools vfs
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

The original prompt says “specified model” but never supplies one.

The upstream Forms handler inserts each question at index zero.
The Forms CLI calls the same original handlers as MCP, so the index-zero
insertion behavior is shared, not a mock-only regression. The mail and
Python interfaces are different: raw RFC 5322 sending makes encoding the
caller's responsibility, and Pyodide lacks native subprocesses. Those are
benchmark surface/environment differences.
