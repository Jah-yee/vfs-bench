# logical-datasets-collection

Original Toolathlon task using filesystem + scholarly + arxiv_local + pdf-tools + fetch. The task statement, initial workspace and evaluator come from the pinned original checkout. Each arm receives a fresh copy of the original files.

The VFS surface uses a disk mount and separate CLIs. Search invokes the original Serper local-tool handler, and fetch invokes the locked original server handlers directly. Exact requests reuse shared response captures with timestamps and hashes outside the agent workspace. New requests still access the live public services.

Setup requires a Serper (`serper.dev`) `SERPER_API_KEY` in `.env.development`, the existing paper-server setup, and the locked fetch dependencies.

The original MCP surface and VFS workspace both build. Search schemas match; for tasks that declare fetch, all four original fetch schemas and full sampled responses match. Paper CLI discovery passes. The original file and grader hashes are checked through DVC. No test files were added.

## Heredoc fix verification

Mirage PR [#1056](https://github.com/strukto-ai/mirage/pull/1056) fixed the
leading-backslash heredoc loss tracked in
[#1050](https://github.com/strukto-ai/mirage/issues/1050). The pinned commit's
focused heredoc suite passes 56 tests, and an exact workspace smoke preserves
`\first\nsecond\n` on a RAM mount.
