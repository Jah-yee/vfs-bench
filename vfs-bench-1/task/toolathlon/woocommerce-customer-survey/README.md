# woocommerce-customer-survey

Find completed WooCommerce orders, create the requested Google Forms questionnaire, email the customers and save its Drive URL.

The frozen capture contains the original MySQL database, WordPress uploads, workspace template and private completed-order ground truth. Each arm restores it in a fresh E2B sandbox. The original preprocessor leaves an empty Forms collection and mailbox; both are checked before execution.

VFS combines `/woo`, `/mail` and `/work` with separate `woocommerce`, `emails` and
`google-forms` CLIs. Email and Forms commands call the original handlers directly.
MCP runs the original servers; both Forms surfaces use Mirage’s isolated
Forms/Drive API and fixture OAuth credentials. The original grader uses that
same API.

`capture-woocommerce-customer-survey` in `dvc.yaml` records the fixture dependencies. The
`papers-forms-lineage` stage checks original task text, source receipts,
server locks, artifact hashes and CLI timeouts against upstream.
See [setup and shared validation](../README.md#paper-forms-and-canvas-conversions).

```sh
uv run python agent/run_agent.py toolathlon/woocommerce-customer-survey --tools mcp
uv run python agent/run_agent.py toolathlon/woocommerce-customer-survey --tools vfs
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

The original Forms server supports five operations. It does not expose every Google Forms UI setting or a paragraph-text option; the CLI deliberately has the same capability limit.
