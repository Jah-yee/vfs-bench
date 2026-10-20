from services import REPO_ROOT

# Upstream's harness: its TypeScript source in the pinned checkout, and the
# tree `setup/setup.py` installs beside it from upstream's own lock. It is
# started as `make run-harness` starts it, `tsx` on `src/index.ts`
# (`package.json:7`), less `watch`.
HARNESS_DIR = (REPO_ROOT / "submodule" / "mcp-atlas" / "services" /
               "agent-harness")
HARNESS_ENTRY = HARNESS_DIR / "src" / "index.ts"
TSX = HARNESS_DIR / "node_modules" / "tsx" / "dist" / "cli.mjs"
SETUP = "uv run python setup/setup.py"

# Its log, beside the one it writes under its working directory itself.
HARNESS_LOG = "agent-harness.log"

# Seconds the harness may take to answer `/health` once started.
HARNESS_START = 60

# Seconds the harness waits on a tool call before it tells the model `Tool
# call timed out after 60s` and moves on: `toolCallTimeoutMs` (`config.ts:25`),
# which `harness.start` leaves at its default. The harness stops waiting but
# never aborts the request (`sandbox-client.ts:207`).
TOOL_CALL_TIMEOUT = 60

# Seconds an idle connection from the harness to this repo's own servers, the
# model proxy and the relay, stays open. The harness keeps its connections
# alive between requests, and one it sends just as uvicorn closes the
# connection as idle, after its default 5, fails with `read ECONNRESET`, which
# the harness does not retry: the run ends as a `ModelError` that is this
# repo's server's, not the model's. So they stay open as long as a run lasts.
KEEP_ALIVE = 24 * 60 * 60

# The bearer token the harness sends with each model request. A placeholder:
# the gateway's key is this process's to send, and never reaches the harness.
LLM_API_KEY = "local"

# The harness's own routes (`index.ts:22`, `:27`), and the two it expects of
# the services it is pointed at: its model proxy's (`litellm-strategy.ts:27`)
# and its sandbox's call (`sandbox-client.ts:207`).
HEALTH = "/health"
RUN_AGENT = "/v2/mcp_eval/run_agent"
COMPLETIONS = "/v1/chat/completions"
CALL_TOOL = "/call-tool"

# `run_eval.py`'s default, which it names in every request. The harness
# reads it only for its logs and for a registry of disabled tools that is
# empty (`mcp-server-configs.ts:16`); the image that serves is the dataset's.
IMAGE = "ghcr.io/scaleapi/mcp-atlas:1.2.7"

# `agent-eval.ts:19`, which a request leaves to the harness unless it sets
# one, as `run_eval.py` does unless asked.
DEFAULT_MAX_TURNS = 256

# The mirage arm's tools, served to upstream's app as its only server: the
# key the app's config names that server by, which never reaches the model,
# and the path it answers on.
TOOL_SERVER = "mirage"
TOOL_SERVER_PATH = "/mcp"

# How a run ended, as the dump records it: finished, stopped by one of the
# harness's two limits (`agent-eval.ts:300`, `:306`), or ended by something
# the harness reports no reason for.
COMPLETED = "completed"
LIMITS = {
    "max_tool_calls_reached": "MaxToolCallsExceeded",
    "max_turns_reached": "MaxTurnsExceeded",
}
WALL_CLOCK = "WallClockExceeded"
HARNESS_ERROR = "HarnessError"
MODEL_ERROR = "ModelError"

# Divergence: how a Gemini model is asked. Upstream's harness posts every
# request, in Chat Completions form, to a LiteLLM proxy -- its model names
# are LiteLLM's, `gemini/...` and `fireworks_ai/...` (`litellm-strategy.ts:18`)
# -- so what a Gemini model is sent is what LiteLLM's Gemini adapter makes of
# that request: each tool's schema rewritten into Gemini's
# (`_build_vertex_schema`, which among other things turns an enum's `""` into
# null, since Gemini refuses an empty value, and every Oxylabs tool declares
# three), and the conversation into Gemini's `contents`. This repo's gateway
# converts Chat Completions for Gemini its own way and passes the `""` through,
# so Gemini refused every request that carried an Oxylabs tool. A Gemini model
# is therefore asked through LiteLLM's adapter here too, in process, against
# the gateway's native Gemini endpoint. The gateway names the model
# `google/<model>` where LiteLLM names it `gemini/<model>`, as with the judge
# (`task/mcpatlas/script/grade_task.py`).
GEMINI = "google/"

# How a Claude model is asked: on Anthropic's own API, through LiteLLM's
# Anthropic adapter in process, which is what upstream's proxy does with a
# request for `anthropic/<model>` (its README's "Anthropic-via-LiteLLM").
# The name is LiteLLM's, and the run's `--base-url` and key are Anthropic's.
ANTHROPIC = "anthropic/"

# Divergence: how an OpenAI model is asked. Upstream's proxy hands a Chat
# Completions request to OpenAI as it is. The gateway's Chat Completions
# endpoint does not: a tool message whose text parses as JSON it parses and
# writes back out with Go's `encoding/json` -- keys sorted, `<`, `>` and `&`
# as `<` and the like, numbers normalised, whitespace dropped -- and an
# array of content parts it writes out whole, as JSON. So the model read a
# JSON tool result neither arm returned, a Slack mention as `<@U...`,
# and was charged for about half of it. The gateway's Responses endpoint
# hands a `function_call_output` over as written, and charges a conversation
# with no JSON in it what Chat Completions does, token for token, so an OpenAI
# model is asked there, the conversation converted item for item. One
# difference remains that no setting here explains: replaying one Atlas turn,
# the model asked for several tools at once 57% of the time through the
# gateway's Chat Completions (104 of 182) and 33% here (69 of 212), with the
# same prompt charged, and effort, `strict`, sampling, storage, streaming and
# the order of calls and outputs ruled out. Both endpoints reach the same
# deployment, so it is in how the gateway converts a request, which it does
# not show.
OPENAI = "openai/"

# The request parameters with a Responses spelling here: the one a draw
# sets. Any other fails the request rather than reaching the model as
# nothing.
RESPONSES_PARAMETERS = {"reasoning_effort"}

# Why a Responses reply stopped short, as Chat Completions spells it.
CUT = {"max_output_tokens": "length", "content_filter": "content_filter"}

# The gateway's native endpoint reads only the camelCase spelling of these
# fields, where Google's own API reads either and LiteLLM writes the
# snake_case one; and it writes an unset field as null, where Google leaves it
# out and LiteLLM takes a null for a value. Neither rewrite changes what the
# model is sent or what it answered. A field the gateway cannot read it drops
# without a word -- the mirage arm's system message went missing that way,
# and only its token count showed it -- so any other snake_case field fails
# the request rather than reaching the model as nothing.
CAMEL = {
    "system_instruction": "systemInstruction",
    "function_declarations": "functionDeclarations",
    "function_call": "functionCall",
    "function_response": "functionResponse",
}
