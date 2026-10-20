# canvas-art-quiz

Original Canvas service and Art History course in E2B. `/canvas` reads
live objects; the separate `canvas` CLI creates quizzes and questions.
The original grader checks persisted questions and correct answers.
Both surfaces use the teacher identity in upstream `other_key.py`, matching
its seeder and grader; this launch divergence is declared in the MCP builder.

Each measured arm owns a fresh sandbox through grading, then deletes it.
Prompts and fixtures come from the pinned Toolathlon checkout. DVC tracks
the captured artifacts and dependency sources; run records include image
digests and source hashes. No task-specific canned SQL responses are used.

After the usual repository setup, export `E2B_API_KEY` and install:

```sh
uv run python -m server.mcp.setup_kubernetes
uv run python -m server.mcp.setup_commerce_canvas
uv run python server/kubernetes_template.py
```

Live integration (requires E2B credentials):

```sh
uv run python tests/business_tasks.py BusinessTasks.test_canvas_art_quiz
```

The Canvas mount now checks access before listing synthetic branches. A teacher
without a personal submission no longer sees a phantom `submission.json`, and
course membership no longer implies readable account directories. Missing or
denied paths use filesystem errors; rate limits and server failures remain visible.

## Current CLI and lineage

`canvas` now invokes the pinned original tool handlers directly, without an
MCP client. Commands drop the `canvas_` prefix and retain the original
schemas, pagination, defaults and response text. Use `canvas --help` and
`canvas <command> --help`. The filesystem mount still enumerates complete
REST collections independently of CLI pagination. Python is for processing
files and data; invoke service commands directly in the shell.

The `service-mcp-tools` DVC stage installs the original dependency locks and
derives `vendor/canvas-mcp/tools.json` and `source.json`. Both arms verify
the recorded tool implementation and schema hashes before startup. Existing
fixture captures retain their DVC source links and bytes.
