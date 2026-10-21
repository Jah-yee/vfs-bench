# Running Your Own Model

Any model behind an OpenAI-compatible Chat Completions endpoint runs on both
datasets and both arms, with no code change.

## What You Provide

- **Endpoint**: the base URL of an OpenAI-compatible API, such as vLLM,
  SGLang, Ollama, LiteLLM or OpenRouter (`http://localhost:8000/v1`).
- **Model id**: the name your endpoint serves the model under. Do not start
  it with `google/`, `anthropic/` or `openai/`: those prefixes select the
  built-in Gemini, Anthropic Messages and (on MCP-Atlas) OpenAI Responses
  adapters.
- **API key**: in an environment variable of your choice, set in
  `.env.development`. Any non-empty value works for a server that checks none.
- **Reasoning effort**: `none`, `low`, `medium`, `high`, `xhigh` or `max`,
  sent as `reasoning_effort`; `default` leaves the field out.

## What the API Must Support

- `POST /v1/chat/completions`, without streaming.
- Tool calling: `tools` in the request, `tool_calls` in the reply and
  `role: "tool"` results in the next request. On vLLM, start the server with
  `--enable-auto-tool-choice --tool-call-parser <parser>`.
- `usage` with `prompt_tokens` and `completion_tokens` on every reply: tokens
  are what the benchmark measures.
- The `max_tokens` and `parallel_tool_calls` fields. Toolathlon sends
  `max_tokens: 65536` and `parallel_tool_calls: true`; MCP-Atlas sends
  neither.
- A context window that fits the conversation plus that completion budget.
  When the context runs out, the error must say `maximum context length`
  (vLLM's does), so the run clears its context as upstream's harness does
  instead of failing.
- The `reasoning_effort` field, or run with `--reasoning-effort default`.

## Run

From `vfs-bench-1/`, run both arms with the same flags, one after the other:

```bash
echo 'MY_MODEL_KEY=sk-...' >> .env.development
for tools in vfs mcp; do
  uv run python agent/run_agent.py toolathlon/nhl-b2b-analysis \
    --model my-org/my-model --base-url http://localhost:8000/v1 \
    --api-key-env MY_MODEL_KEY --reasoning-effort medium --tools $tools
done
```

Each run writes its dump, named after the model, to `dumps/`, and grades
itself.

## Service Credentials

Besides the model, a task needs keys only for the live services it calls.
Set them in `.env.development`; `.env.example` says where to get each.

| Tasks | Toolathlon | MCP-Atlas |
| --- | --: | --: |
| Fully simulated: local fakes and fixtures only | 42 | 8 |
| Live public services, no key | 9 | 21 |
| At least one key | 49 | 71 |

The simulated services are Google Workspace, Notion, GitHub, Slack, Airtable,
mail, Snowflake, BigQuery, W&B, MongoDB and the Hugging Face Hub. Live public
services without a key include the browser, fetch, arXiv and Scholar, Yahoo
Finance, PubMed and OpenStreetMap.

How many tasks need each key (one task can need several):

| Credential | Toolathlon | MCP-Atlas |
| --- | --: | --: |
| `E2B_API_KEY` (Canvas, WooCommerce, Kubernetes and E2B sandboxes) | 21 | 23 |
| `SERPER_API_KEY` (web search) | 24 | |
| `EXA_API_KEY` | | 27 |
| `OXYLABS_USERNAME`, `OXYLABS_PASSWORD` | | 20 |
| `WIKIPEDIA_ACCESS_TOKEN` | | 19 |
| `WEATHER_API_KEY` | | 19 |
| `NPS_API_KEY` | | 11 |
| `GOOGLE_MAPS_API_KEY` | 6 | 5 |
| `BENCH_S3_*` and `AWS_*` (`k8s-mysql`, `k8s-pr-preview-testing`) | 2 | |
| `YOUTUBE_API_KEY` (`youtube-repo`) | 1 | |
| `GOOGLE_APPLICATION_CREDENTIALS` (`fillout-online-forms`) | 1 | |

## MCP-Atlas Grading

Toolathlon's graders call no model. MCP-Atlas's grader asks an LLM judge,
`google/gemini-3.1-pro-preview`, at the run's `--base-url` with the run's key,
so the endpoint must serve that model as well. With a self-hosted model, put a
router in front that sends your model to your server unchanged and the judge
to a gateway that serves Gemini.

## Not OpenAI-Compatible?

Serve the model behind an OpenAI-compatible server first. A provider that
needs its own request format is an adapter in code, as `agent/claude.py` and
`agent/gemini.py` are for Toolathlon's loop and `agent/atlas/gateway.py` is for
MCP-Atlas; declare its divergence there.
