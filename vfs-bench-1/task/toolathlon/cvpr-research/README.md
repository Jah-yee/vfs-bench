# cvpr-research

Original Toolathlon task using filesystem + fetch + playwright_with_chunk. The task statement, initial workspace and evaluator come from the pinned original checkout. Each arm receives a fresh copy of the original files.

The VFS surface uses a disk mount and separate CLIs. Search invokes the original Serper local-tool handler, and fetch invokes the locked original server handlers directly. Exact requests reuse shared response captures with timestamps and hashes outside the agent workspace. New requests still access the live public services. Browser tasks run in a local container.

Setup requires a Serper (`serper.dev`) `SERPER_API_KEY` in `.env.development`, the locked fetch and browser dependencies.

The original MCP surface and VFS workspace both build. Search schemas match; for tasks that declare fetch, all four original fetch schemas and full sampled responses match. Browser CLI discovery passes. The original file and grader hashes are checked through DVC. No test files were added.
