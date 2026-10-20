import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

NAME = "toolathlon-gym"

# Toolathlon-GYM is Toolathlon's format at eight times the scale: 503 tasks
# against 109, disjoint from them, in the same directory shape and graded by
# the same kind of script. So this seam is `toolathlon`'s with one checkout
# swapped -- and every line below that is *not* a swap is a place the two
# genuinely differ, which is the only reason to read this file.
CHECKOUT = ("submodule", "toolathlon_gym")

# One checkout, named twice. `Launch.vendored` asks the seam for `gym()`
# because Toolathlon's own configs reach into GYM's `local_servers/` for six
# of their servers -- Toolathlon's arm has been running GYM's vendored trees
# all along. Here the two are the same directory, which is what makes the
# server builders below so short.
GYM = CHECKOUT

POOL = ("tasks", "finalpool")

# Upstream refuses to grade a run that did not end in `TaskStatus.SUCCESS`,
# reporting `pass: None` before it builds the command
# (`utils/evaluation/evaluator.py:47`). Grading takes the same gate here, so
# an arm that hit the wall clock or raised is not measured against a fixture
# it never finished changing. Declared rather than assumed: a dataset whose
# runner scores the agent's last message has an answer to grade even when the
# run was cut short, and inheriting this rule would discard it.
GRADES_UNFINISHED = False

LOCAL = ("task", NAME)
MANIFEST = ("task.json", )

# Not `server/seed/seed_task.py`. That one dispatches Toolathlon's fixture
# kinds against this repo's fakes; a GYM task states its setup as its own
# `preprocess/main.py`, so this dataset's seeder runs that instead.
SEEDER = ("task", NAME, "script", "seed_task.py")

PROMPT = ("docs", "agent_system_prompt.md")
CONFIG = ("task_config.json", )
WORKSPACE = ("initial_workspace", )
EVALUATOR = ("evaluation", "main.py")

# What a GYM task has that a Toolathlon one does not: the setup script is
# shipped rather than declared, and the answer is shipped beside it.
PREPROCESS = ("preprocess", "main.py")
GROUNDTRUTH = ("groundtruth_workspace", )

# Global here, per-task upstream. 57 Toolathlon tasks carry their own
# `token_key_session.py`; no GYM task does, because its services are one
# local Postgres rather than a spread of accounts.
TOKENS = ("configs", "token_key_session.py")

# `scripts/eval_config.json`: `max_steps_under_single_turn_mode: 100`, which
# `run_containerized.sh` also passes as its default. Toolathlon's 60 is a
# different number for the same knob and must not be inherited.
MAX_TURNS = 100

# Never sent. GYM drives CAMEL's `ChatAgent`, whose request carries no
# `parallel_tool_calls`, so the provider default stands and the SDK omits the
# parameter for None (`openai_chatcompletions.py:576`). Toolathlon's False is
# read off `utils/data_structures/agent_config.py:11` and is upstream's there,
# not here.
PARALLEL_TOOL_CALLS = None

# ---------------------------------------------------------------------------
# The one divergence in this file, stated once and in full.
#
# GYM's harness is CAMEL: `utils/roles/task_agent.py` drives a
# `camel.agents.ChatAgent` with `max_iteration=100`, over tools built by
# `camel.toolkits.MCPToolkit`. This repo runs the `openai-agents` loop on
# GYM's tasks instead -- a deliberate choice, taken so the first GYM task
# could be measured without a third harness, and not a claim that the two are
# the same. They are not, in four ways that all change what the model is sent:
#
#   1. Tool schemas. `_sanitize_tool_schemas` (`task_agent.py:99`) rewrites
#      every definition before it goes out: strips `strict` and
#      `additionalProperties: false`, drops `enum` from non-string fields, and
#      gives untyped array items a `type: string`. The agents runner sends
#      what the server declared.
#   2. Tool results, capped at 8,000 chars there, at this repo's
#      `MAX_SINGLE_TURN_RETURN_CHARS` here.
#   3. The system prompt, which CAMEL appends a claim_done sentence to and
#      then rewrites `local-claim_done` to `claim_done` in.
#   4. The local tools -- see LOCAL_TOOLS below, which is the expensive one.
#
# Closing it means running CAMEL's loop on `camel-ai` at GYM's own pin, the
# way `agent/atlas/` runs MCP-Atlas's. Until then this line
# is the declaration, and `task/toolathlon-gym/README.md` carries the numbers.
LOOP = "agents"

# And the consequence of (4), which is worth its own paragraph because it
# lands entirely on the arm this repo measures against.
#
# GYM's `_build_local_tools` (`task_agent.py:190`) resolves the same five
# declared names to *six* tools: claim_done, python_execute, the two overlong
# helpers, and one stub apiece for manage_context and history -- CAMEL manages
# its own memory, so those two are `async def(action="") -> "OK"`. Toolathlon's
# `local_tool_mappings` resolves them to fourteen, because its `manage_context`
# is three tools and its `history` five, all real.
#
# So running Toolathlon's harness hands the MCP arm eight tools GYM never
# shows it, and the mirage arm gets none of them either way. That inflates the
# denominator, which is to say it flatters this repo's own number. It is
# declared here rather than quietly corrected because the harness was chosen
# whole; the fix is the camel loop above, not a hand-picked subset of it.
LOCAL_TOOLS = {
    "python_execute":
    ("utils.aux_tools.python_interpretor", "tool_python_execute"),
    "claim_done": ("utils.aux_tools.basic", "tool_done"),
    "sleep": ("utils.aux_tools.basic", "tool_sleep"),
    "web_search": ("utils.aux_tools.web_search", "tool_web_search"),
    "ai_webpage_summary":
    ("utils.aux_tools.ai_webpage_summary", "tool_ai_webpage_summary"),
    "manage_context":
    ("utils.aux_tools.context_management_tools", "context_management_tools"),
    "history": ("utils.aux_tools.history_tools", "history_tools"),
    "handle_overlong_tool_outputs":
    ("utils.aux_tools.overlong_tool_manager", "overlong_tool_tools"),
}

# Those modules live in Toolathlon's checkout, not GYM's: GYM ships three
# aux_tools files to Toolathlon's eight, and they are CAMEL-shaped factories
# rather than ready tools. Running Toolathlon's harness means importing
# Toolathlon's implementations of it, so this seam needs both checkouts.
TOOLS_CHECKOUT = ("submodule", "Toolathlon")

# No timeout table. `mcp_servers.timeout_for` falls through to
# `upstream_config`, which reads `configs/mcp_servers/<name>.yaml` out of
# `root()` at its pinned commit -- and `root()` is GYM here, so the fallthrough
# reads GYM's own yaml without this file restating a single number. The four
# servers below happen to agree with Toolathlon's, and declaring them would
# have hidden the day they stop.


def root() -> Path:
    """The dataset's checkout, with its packages importable.

    Args:
        None.

    Returns:
        Path: the checkout root.
    """
    found = Path(
        os.environ.get("TOOLATHLON_GYM_ROOT",
                       REPO_ROOT.joinpath(*CHECKOUT))).expanduser().resolve()
    if str(found) not in sys.path:
        sys.path.insert(0, str(found))
    return found


def gym() -> Path:
    """Where the vendored MCP server trees live, which is this checkout.

    Returns:
        Path: the checkout root.
    """
    return root()


def tools_root() -> Path:
    """Toolathlon's checkout, which the local tools are imported from.

    On the path for the reason `root` puts GYM there: `LOCAL_TOOLS` names
    `utils.aux_tools.*`, and both checkouts spell that package, so whichever
    is imported first wins. GYM's copy has three of the eight modules and
    factories where the harness wants tools, so it is the wrong one to win --
    and it losing has to be by construction rather than by import order.

    Returns:
        Path: Toolathlon's checkout root.
    """
    found = Path(
        os.environ.get(
            "TOOLATHLON_ROOT",
            REPO_ROOT.joinpath(*TOOLS_CHECKOUT))).expanduser().resolve()
    if str(found) not in sys.path:
        sys.path.insert(0, str(found))
    return found


def seeder() -> Path:
    """What rebuilds this dataset's fixtures before a draw.

    Returns:
        Path: the seeder, run once per arm.
    """
    return REPO_ROOT.joinpath(*SEEDER)


def local(task: str) -> Path:
    """Where this repo keeps its own files for one task.

    Args:
        task (str): the task name.

    Returns:
        Path: the directory, whether or not it exists.
    """
    return REPO_ROOT.joinpath(*LOCAL, task)


def tasks() -> list[str]:
    """Every task this repo carries its own half of.

    Returns:
        list[str]: task directory names, sorted.
    """
    pool = REPO_ROOT.joinpath(*LOCAL)
    return sorted(d.name for d in pool.iterdir()
                  if (d / "shared" / "task.md").is_file())


def manifest(task: str) -> Path:
    """The fixture manifest, which says what a draw starts from.

    Args:
        task (str): the task name.

    Returns:
        Path: the manifest.
    """
    return local(task).joinpath(*MANIFEST)


def task_dir(task: str) -> Path:
    """Where this dataset keeps one task's own files.

    Args:
        task (str): the task name.

    Returns:
        Path: the task directory inside the checkout.
    """
    return root().joinpath(*POOL, task)


def config(task: str) -> dict:
    """The task's declaration, as the dataset writes it.

    Args:
        task (str): the task name.

    Returns:
        dict: the parsed declaration.
    """
    return json.loads(task_dir(task).joinpath(*CONFIG).read_text())


def needed_mcp_servers(task: str) -> list[str]:
    """The MCP servers this dataset says the task needs.

    Args:
        task (str): the task name.

    Returns:
        list[str]: server names.
    """
    return list(config(task)["needed_mcp_servers"])


def needed_local_tools(task: str) -> list[str]:
    """The local tools this dataset says the task needs.

    Args:
        task (str): the task name.

    Returns:
        list[str]: declared names, in declaration order.
    """
    return list(config(task).get("needed_local_tools") or [])


def prompt(task: str) -> Path:
    """The system prompt the MCP arm is given.

    Args:
        task (str): the task name.

    Returns:
        Path: the prompt file.
    """
    return task_dir(task).joinpath(*PROMPT)


def tokens(task: str) -> Path:
    """The `${token.*}` session several server configs resolve.

    One file for the whole dataset rather than one per task, so the argument
    is taken for the seam's shape and ignored.

    Args:
        task (str): the task name, unused.

    Returns:
        Path: the file.
    """
    return root().joinpath(*TOKENS)


def initial_workspace(task: str) -> Path:
    """The starting workspace both arms are given.

    182 of the 503 tasks ship none, this one among them: an empty workspace
    is the starting state, and `preprocess/main.py` only has to make sure it
    is empty.

    Args:
        task (str): the task name.

    Returns:
        Path: the directory, which may not exist.
    """
    return task_dir(task).joinpath(*WORKSPACE)


def preprocess(task: str) -> Path:
    """The task's own setup script, which the seeder runs.

    Args:
        task (str): the task name.

    Returns:
        Path: the script, which every task ships.
    """
    return task_dir(task).joinpath(*PREPROCESS)


def groundtruth(task: str) -> Path:
    """The answer the evaluator compares against.

    Args:
        task (str): the task name.

    Returns:
        Path: the directory, which may not exist.
    """
    return task_dir(task).joinpath(*GROUNDTRUTH)


def evaluator(task: str) -> Path:
    """The evaluator that grades a run.

    Args:
        task (str): the task name.

    Returns:
        Path: the evaluator.
    """
    return task_dir(task).joinpath(*EVALUATOR)


def evaluator_argv(task: str) -> tuple[list[str], Path]:
    """How this dataset's evaluator has to be invoked, and from where.

    `utils/data_structures/task_config.py:105` builds
    `{python_bin} -m tasks.finalpool.<task>.evaluation.main`, which is
    Toolathlon's shape too: relative imports, run as a module from the
    checkout root.

    Args:
        task (str): the task name.

    Returns:
        tuple: the argv prefix, and the working directory to run it in.
    """
    module = ".".join((*POOL, task, *EVALUATOR)).removesuffix(".main.py")
    return ["uv", "run", "-m", f"{module}.main"], root()


# ---------------------------------------------------------------------------
# The servers, built from `configs/mcp_servers/<name>.yaml` at the pin.
#
# Four, because that is what the one task here declares. A fifth server is a
# fifth builder, and a task naming one this file has no builder for stops the
# draw rather than quietly running Toolathlon's -- which is the whole reason a
# dataset carries its own registry: GYM vendors `howtocook-mcp` at 0.1.1 where
# this repo pins npm's 0.2.2 for Toolathlon, and running the wrong one would
# measure a tool surface nobody ships.


def _vendored(at, *parts: str) -> str:
    """One path inside GYM's `local_servers`, as a string for argv.

    Args:
        at: the `Launch` the builder is given.
        *parts (str): path segments below `local_servers`.

    Returns:
        str: the absolute path.
    """
    return str(at.vendored.joinpath(*parts))


def filesystem(at) -> dict:
    """Node's reference filesystem server, scoped to the workspace.

    `filesystem.yaml`, which points at the vendored `dist/index.js` rather
    than at `npx -y @modelcontextprotocol/server-filesystem` the way
    Toolathlon's does. Same server, and the gitlink is what pins it.

    Args:
        at: the `Launch` the builder is given.

    Returns:
        dict: what `MCPServerStdio` is constructed from.
    """
    return {
        "command": "node",
        "args": [_vendored(at, "filesystem", "dist", "index.js"), at.workdir],
        "cwd": at.workdir,
    }


def excel(at) -> dict:
    """The vendored excel server.

    `excel.yaml`. `--directory` picks the vendored copy; a bare `uv run`
    would look for the entry point in the scratch dir, which is not a
    project.

    Args:
        at: the `Launch` the builder is given.

    Returns:
        dict: what `MCPServerStdio` is constructed from.
    """
    return {
        "command":
        "uv",
        "args": [
            "--directory",
            _vendored(at, "excel-mcp-server"), "run", "excel-mcp-server",
            "stdio"
        ],
        "cwd":
        at.workdir,
    }


def pptx(at) -> dict:
    """The PowerPoint server.

    `pptx.yaml`, vendored where Toolathlon's config runs
    `uvx --from office-powerpoint-mcp-server`, which resolves whatever PyPI
    publishes on the day.

    Args:
        at: the `Launch` the builder is given.

    Returns:
        dict: what `MCPServerStdio` is constructed from.
    """
    return {
        "command":
        "uv",
        "args": [
            "--directory",
            _vendored(at, "Office-PowerPoint-MCP-Server"), "run",
            "ppt_mcp_server"
        ],
        "cwd":
        at.workdir,
    }


# The proxy settings `arms.NO_NETWORK` spells, restated rather than imported
# because a module under `task/` may not depend on `agent/`. Port 9 is
# discard, so a request fails at connect instead of hanging.
NO_NETWORK = {
    "http_proxy": "http://127.0.0.1:9",
    "https_proxy": "http://127.0.0.1:9",
    "HTTP_PROXY": "http://127.0.0.1:9",
    "HTTPS_PROXY": "http://127.0.0.1:9",
    "no_proxy": "localhost,127.0.0.1,::1",
    "NO_PROXY": "localhost,127.0.0.1,::1",
}


def howtocook_corpus() -> Path:
    """The recipe file both of this dataset's surfaces read.

    GYM's vendored 0.1.1 keeps it at `src/data/all_recipes.json` and `tsc`
    copies it to `build/data/`, which is what the server imports -- so that
    is the file, and `cli/cook_cli.py` is pointed at the same one. One file,
    so the two arms cannot drift.

    Returns:
        Path: the corpus inside the vendored server.
    """
    return gym().joinpath("local_servers", "HowToCook-mcp", "build", "data",
                          "all_recipes.json")


def howtocook(at) -> dict:
    """The recipe server, at GYM's vendored copy and not this repo's pin.

    The one server here whose build differs from the shared registry's, and
    the reason this dataset needs a registry at all. `howtocook.yaml` runs
    `${local_servers_paths}/HowToCook-mcp/build/index.js`, which is
    `howtocook-mcp` **0.1.1**; `server/mcp/setup_howtocook.py` pins npm's
    **0.2.2** because that is the corpus Toolathlon's two howtocook tasks
    were graded against. Two versions, two recipe corpora, two tool surfaces.

    Started with the network closed, which is a divergence and a necessary
    one. 0.1.1's `fetchRecipes` (`src/data/recipes.ts:10`) requests
    `https://weilei.site/all_recipes.json` and falls back to the committed
    `all_recipes.json` only when that fails -- so on a machine with network
    the MCP arm reads whatever that site serves today while the mirage arm
    reads the file in the tree, and the same arm reads something different
    next week. Closing the network is what makes the fallback the answer,
    and the fallback is the corpus the gitlink pins. The same reason
    `mcp_servers.TERMINAL_COMMANDS` drops `curl`.

    Args:
        at: the `Launch` the builder is given.

    Returns:
        dict: what `MCPServerStdio` is constructed from.
    """
    return {
        "command": "node",
        "args": [_vendored(at, "HowToCook-mcp", "build", "index.js")],
        "env": {
            **os.environ,
            **NO_NETWORK
        },
        "cwd": at.workdir,
    }


SERVERS = {
    "filesystem": filesystem,
    "excel": excel,
    "pptx": pptx,
    "howtocook": howtocook,
}

# Which servers hold state outside the run's own workspace, and so need this
# repo's fakes up before a draw. None of the four above does: `excel`, `pptx`
# and `filesystem` read and write the workspace, and `howtocook` serves a
# corpus committed inside its own tree. `needs_stack` below is derived from
# this rather than declared per dataset, because GYM is a Postgres-backed
# benchmark whose *other* 502 tasks mostly do need one.
STATEFUL_SERVERS = frozenset({
    "emails", "notion", "github", "google_sheet", "google_calendar",
    "google_forms", "snowflake", "yahoo-finance", "canvas", "woocommerce",
    "memory", "fetch", "google-cloud"
})


def needs_stack(task: str) -> bool:
    """Whether a draw of this task has to bring the fakes up first.

    Derived from the task's own declaration rather than set for the dataset,
    because the answer genuinely varies across GYM's 503: 151 of them want
    Snowflake and 258 want mail, while this one wants four servers that never
    leave the workspace. Asking Docker for those would be a dependency the
    task does not have.

    Args:
        task (str): the task name.

    Returns:
        bool: True when any declared server keeps state outside the run.
    """
    return bool(set(needed_mcp_servers(task)) & STATEFUL_SERVERS)
