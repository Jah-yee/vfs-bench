# academic-pdf-report

VFS curl/wget can no longer fetch unrecorded public responses; browser calls now use the original timeout. Research search/fetch still share an exact-request cache across runs, so per-draw snapshot isolation remains unresolved.

Original Toolathlon task using playwright_with_chunk + excel + terminal + arxiv_local + pdf-tools + fetch. The task statement, initial workspace and evaluator come from the pinned original checkout. Each arm receives a fresh copy of the original files.

The VFS surface uses a disk mount and separate CLIs. Search invokes the original Serper local-tool handler, and fetch invokes the locked original server handlers directly. Searches and pages are read live on both arms each time, and nothing a run fetches is kept. Browser tasks run in a local container.

Setup requires a Serper (`serper.dev`) `SERPER_API_KEY` in `.env.development`, the existing paper-server setup, and the locked fetch and browser dependencies.

The original MCP surface and VFS workspace both build. Search schemas match; for tasks that declare fetch, all four original fetch schemas and full sampled responses match. Paper and browser CLI discovery passes. The original file and grader hashes are checked through DVC.

## Fixed pages — 2026-09-19

The pages this task's answer rests on are captured once into `shared/web_fixture.json`
and served from there on both arms; `capture-web@academic-pdf-report` names each URL and
`verify-web@academic-pdf-report` checks the capture against the grader's truth. A page
not held there, and every web search, is read live each time on both arms,
and nothing a run fetches is kept.
