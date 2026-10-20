# Benchmark resources

A resource exposes a service as files. It owns path mapping, directory
listing, reads, and supported file operations. Benchmark-specific mounts
belong here; reusable resources can move to Mirage after their API settles.

Keep the layers separate:

| Location | Responsibility |
| --- | --- |
| `vfs/` | Filesystem views and file semantics |
| `cli/` | Command syntax, stdin, stdout, and exit status |
| `server/clients/` | Service API access; no mounts or commands |
| `server/mcp/` | Launch the pinned upstream MCP implementation |
| `server/seed/` | Restore original task fixtures |
| `server/sandbox.py` | Sandbox lifetime and transport |
| `server/kubernetes_proxy.py` | Private cluster authentication and proxy lifetime |

Mounts and CLIs may share an API client. Neither calls MCP or provisions a
fixture. Native programs such as `kubectl` use their own client and the same
backend endpoint. Task YAML composes the surfaces.

For Kubernetes, the read-only mount fetches live API objects, `kubectl`
performs mutations, and the upstream MCP server runs unchanged. All connect
to the same cluster within an arm. Each measured arm starts with a new
cluster. Canvas and WooCommerce follow the same boundaries: `vfs/canvas.mjs`
and `vfs/woocommerce.mjs` read live REST objects, while separate CLIs
invoke the pinned original tool handlers through `server/clients/original_tools.mjs`,
without an MCP client. CLI pagination and mutation workflows stay upstream
while mounts enumerate complete collections through the REST client. Canvas
binary transfers use workspace stdin/stdout. The DVC `service-mcp-tools` stage
records original schemas and implementation hashes, verified by both arms.
Their original SQL-backed services run in isolated E2B instances.

Canvas lists synthetic branches only when the current identity can read them:
course access does not imply account access or a personal assignment submission.
Direct missing and denied reads become filesystem `ENOENT` and `EACCES` errors
for both Canvas and WooCommerce. Rate limits and service failures still propagate;
the REST client and original CLI handlers retain their service error messages.

Paper search and Forms operations have separate CLIs rather than artificial
file trees. `cli/toolathlon/papers.mjs` and `cli/toolathlon/forms.mjs` provide command syntax;
workers in `server/clients/` import the pinned original handlers without an
MCP client. Both surfaces use the same service transport and argument schemas.
Paper downloads become ordinary files under `/work/arxiv_local_storage`;
LaTeX source is returned on stdout. Backend HTTP caches and logs are kept
outside `/work`. Forms uses Mirage's fixture API with the original server's
five-operation capability limit.
