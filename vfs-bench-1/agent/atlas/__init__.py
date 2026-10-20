from atlas.harness import run
from atlas.sandbox import serve

# MCP-Atlas's own harness, run rather than reproduced. Upstream's loop is a
# TypeScript service, `services/agent-harness`: no agent framework, a
# hand-written `for` loop (`agent-eval.ts`) that asks the model over Chat
# Completions at `LLM_BASE_URL` and reaches every tool through one HTTP app
# at `MCP_SANDBOX_URL`, `services/agent-environment`, which owns the MCP
# servers. Both arms run that harness, from the pinned checkout, against
# that app, in upstream's image: the MCP arm's app serves the task's
# servers, the mirage arm's serves the shell. So everything between the
# model and a tool is upstream's code -- the loop, its limits and retries,
# the 60 s bound on a call, what a failure or an empty result reads as --
# and the surface is the only thing that differs.
#
# - `sandbox`: which app each arm's harness reaches, and `tools`, the
#   mirage arm's tools as the one server its app is given.
# - `harness`: upstream's harness, started and handed one task.
# - `proxy`: what stands where upstream's LiteLLM proxy stands, asking the
#   model through `gateway` in the two ways `constants` declares.
# - `relay`: the app, passed on byte for byte, each tool call timed.
# - `outcome`: the harness's answer, in the form the dump is written from.
__all__ = ["run", "serve"]
