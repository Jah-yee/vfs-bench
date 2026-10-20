# find-alita-paper

Find the latest version of the Alita paper, save its PDF under the requested filename, and return the title, arXiv URL and code repository.

Every arXiv and Scholar request is answered live on both arms each time it is made, and nothing a run fetches is kept: each run records every request with its time and response hash.

MCP runs Toolathlon’s unmodified arxiv-local retry wrapper and original Scholarly fork in their locked Python environments. The separate `arxiv-local` and `scholarly` CLIs call those same handlers. Downloaded papers are exposed under `/work/arxiv_local_storage`; backend caches and logs remain outside `/work`. No E2B or additional API credentials are needed.

Original tool names, descriptions and argument schemas match the CLI, and sampled search results matched in full. Native and VFS file commands are denied access to the private backend cache.

The
`papers-forms-lineage` stage checks original task text, source receipts,
server locks, artifact hashes and CLI timeouts against upstream.
See [setup and shared validation](../README.md#paper-forms-and-canvas-conversions).

```sh
uv run python agent/run_agent.py toolathlon/find-alita-paper --tools mcp
uv run python agent/run_agent.py toolathlon/find-alita-paper --tools vfs
```
