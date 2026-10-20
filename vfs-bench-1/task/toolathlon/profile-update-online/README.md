# profile-update-online

Original Toolathlon task using filesystem + playwright_with_chunk + scholarly + arxiv_local + pdf-tools. The task statement, initial workspace and evaluator come from the pinned original checkout. Each arm receives a fresh copy of the original files.

The original preprocessing extracts `files.tar.gz` and removes the archive before the agent starts; both arms apply that step.

The VFS surface uses a disk mount and separate CLIs. Search invokes the original Serper local-tool handler. Exact requests reuse shared response captures with timestamps and hashes outside the agent workspace. New requests still access the live public services. Browser tasks run in a local container.

Setup requires a Serper (`serper.dev`) `SERPER_API_KEY` in `.env.development`, the existing paper-server setup, and the locked browser dependencies.

The original MCP surface and VFS workspace both build. Search schemas and sampled live responses match. Paper and browser CLI discovery passes. The original file and grader hashes are checked through DVC. No test files were added.
