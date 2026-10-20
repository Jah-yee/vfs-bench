import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tarfile
from contextlib import ExitStack, contextmanager, nullcontext
from functools import cache
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[2]

NAME = "toolathlon"

# Upstream's two checkouts. Here rather than in `services.py` because both
# are named after this dataset, and a module `task/` imports must not
# depend on `agent/`.
CHECKOUT = ("submodule", "Toolathlon")
GYM = ("submodule", "toolathlon_gym")

# Where this dataset keeps a task, and what it calls each of the files the
# harness needs. Every one of these was spelled inline in `arms.py`,
# `grading.py`, `mcp_servers.py` and `grade_task.py`; a second dataset would
# have meant editing all four.
POOL = ("tasks", "finalpool")

# Upstream refuses to grade a run that did not end in `TaskStatus.SUCCESS`,
# reporting `pass: None` before it builds the command
# (`utils/evaluation/evaluator.py:47`). Grading takes the same gate here, so
# an arm that hit the wall clock or raised is not measured against a fixture
# it never finished changing. Declared rather than assumed: a dataset whose
# runner scores the agent's last message has an answer to grade even when the
# run was cut short, and inheriting this rule would discard it.
GRADES_UNFINISHED = False


@cache
def parallel_config() -> dict:
    """Read one complete profile from the pinned upstream runner."""
    import re
    source = subprocess.check_output(
        ["git", "-C",
         str(root()), "show", "HEAD:scripts/run_parallel.sh"],
        text=True)
    values = {
        key: int(re.search(rf'^{key}="(\d+)"', source, re.MULTILINE)[1])
        for key in ("MAX_STEPS", "MAX_TOKENS", "TIMEOUT")
    }
    template = source.split('cat > "$CONFIG_FILE" <<EOF',
                            1)[1].split("\nEOF", 1)[0]
    for key, value in {
            **values, "MODEL_NAME": "model",
            "MODEL_PROVIDER": "unified"
    }.items():
        template = template.replace("$" + key, str(value))
    config = json.loads(template)
    config["timeout"] = values["TIMEOUT"]
    return config


def __getattr__(name: str):
    paths = {
        "MAX_TURNS":
        ("global_task_config", "max_steps_under_single_turn_mode"),
        "MAX_TOKENS": ("agent", "generation", "max_tokens"),
        "PARALLEL_TOOL_CALLS": ("agent", "tool", "parallel_tool_calls"),
        "TIMEOUT": ("timeout", ),
    }
    if name not in paths:
        raise AttributeError(name)
    value = parallel_config()
    for key in paths[name]:
        value = value[key]
    return value


@cache
def system_prompts_type():
    """Load the unchanged upstream class without its unrelated task imports."""
    import ast
    import dataclasses
    import typing
    source = subprocess.check_output([
        "git", "-C",
        str(root()), "show", "HEAD:utils/data_structures/task_config.py"
    ],
                                     text=True)
    node = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef) and node.name == "SystemPrompts")
    namespace = {
        "dataclass": dataclasses.dataclass,
        "Union": typing.Union,
        "Dict": dict,
        "os": os
    }
    exec(
        compile(ast.Module(body=[node], type_ignores=[]),
                "upstream:SystemPrompts", "exec"), namespace)
    return namespace["SystemPrompts"]


CLAIM_DONE = ("you can either call the `local-claim_done` tool or respond "
              "without calling any tool")


def apply_system_prompt(prompt: str,
                        task: str,
                        workdir: str,
                        *,
                        shell: bool = False) -> str:
    """Apply upstream substitutions and single-turn mode to either arm."""
    from datetime import datetime
    root()
    SystemPrompts = system_prompts_type()
    from grading import seeded_at
    if shell:
        # Carry the clock only when upstream supplies it to this task.
        source = (task_dir(task) / "docs/agent_system_prompt.md").read_text()
        clock = [
            line for line in source.splitlines()
            if "!!<<<<||||time||||>>>>!!" in line
        ]
        if clock:
            prompt += "\n" + "\n".join(clock)
        # Upstream's way to finish, less `local-claim_done`: this arm's one
        # tool is the shell.
        done = [
            line.replace(CLAIM_DONE,
                         "respond without calling the `shell` tool")
            for line in source.splitlines() if CLAIM_DONE in line
        ]
        if done:
            prompt += "\n" + "\n".join(done)
    timestamp = datetime.fromisoformat(seeded_at(
        local(task))).strftime("%Y-%m-%d %H:%M:%S %A")
    return SystemPrompts(agent=prompt,
                         user=None).apply(workdir,
                                          "",
                                          timestamp,
                                          single_turn_mode=True).agent


# And which loop drives it. `openai-agents` is not this repo's choice here:
# upstream Toolathlon is built on it (it pins `openai-agents==0.0.15`, which
# is the whole reason this repo carries a second virtualenv), so the agents
# runner *is* upstream's harness shape.
LOOP = "agents"

# And where this repo keeps its own half of a task -- the fixtures, the two
# arms' configs, the manifest. `task/<dataset>/<task>/`, so a second
# benchmark's tasks sit beside these rather than mixed in among them.
LOCAL = ("task", NAME)


def shell_cwd(task: str) -> str | None:
    """Honor the workspace profile before the legacy research default."""
    import yaml

    path = local(task) / 'vfs/workspace.yaml'
    if path.is_file():
        workspace = yaml.safe_load(path.read_text())
        cwd = workspace.get('profiles', {}).get('default', {}).get('cwd')
        if cwd is not None:
            return cwd
    from server.seed.research import TASKS
    return "/work" if task == "latex-prompt-box" or task in TASKS else None


def workspace_config(body: dict) -> None:
    """Let upstream's result handler preserve output before truncating it.

    Every session runs under `task_paths.py`, which refuses a read or a
    listing outside the task's mounts and a walk of `/`, as upstream's
    terminal refuses a path outside its workspace. It is asked before a
    line runs, to refuse the line whole, and before each command.

    Args:
        body (dict): the task's workspace yaml, as loaded.
    """
    from mirage.policy.builtin.output_cap import DEFAULT_COMMAND_LIMITS

    for runtime in body.get("runtimes", []):
        if isinstance(runtime, dict) and runtime.get("name") == "pyodide":
            runtime.setdefault("config", {}).setdefault(
                "packageBaseUrl",
                os.environ.get("PYODIDE_PACKAGES",
                               str(REPO_ROOT / "vendor/pyodide-packages")))

    # Mirage's default line caps discard bytes before the Toolathlon
    # runner can save them. Keep its timeouts and explicit task overrides;
    # the runner owns the upstream character cap and recovery files.
    for mount in body.get("mounts", {}).values():
        limits = mount.setdefault("command_limits", {})
        for command, default in DEFAULT_COMMAND_LIMITS.items():
            limits.setdefault(command, {
                "timeout_seconds": default.timeout_seconds,
            })
    body.setdefault("profiles", {}).setdefault("default", {})["policy"] = {
        method: [{
            "script": str(Path(__file__).parent / "task_paths.py"),
            "runtime": "monty",
        }]
        for method in ("pre_execute", "pre_command")
    }


@cache
def terminal_output_limits() -> tuple[int, int, str]:
    """Copy the original terminal's stream caps and truncation marker."""
    import yaml

    from server.mcp.mcp_servers import upstream_config
    env = yaml.safe_load(upstream_config("terminal"))["params"]["env"]
    return (int(env["MAX_STDOUT_LENGTH"]), int(env["MAX_STDERR_LENGTH"]),
            env.get("OUTPUT_TRUNCATE_MESSAGE", "...[output truncated]"))


# Why `task_paths.py` refused a command. Mirage prints such a refusal in
# bash's own voice, `<command>: Permission denied`, and keeps the reason on
# the result's record; its own agent adapters print it as one more line. A
# line refused whole says so on stderr; a command refused where it stands
# says so where its stderr goes, so `2>&1` puts it on stdout.
REFUSED_PATH = ("only the paths VFS.md lists belong to the task; name one of "
                "those instead")


def shell_output(task: str, command: str, stdout: str, stderr: str) -> str:
    """Cap terminal output after execution; keep paper-tool reads whole.

    A command `task_paths.py` refused gets the line Mirage's own agent
    adapters print for it, `policy denied: <reason>`.

    Args:
        task (str): the task name.
        command (str): the command line the model sent.
        stdout (str): its standard output.
        stderr (str): its standard error.

    Returns:
        str: stdout and stderr, and a line for each refusal.
    """
    if task == "latex-prompt-box":
        try:
            words = list(
                shlex.shlex(command, posix=True, punctuation_chars=True))
        except ValueError:
            words = []
        # A direct service call corresponds to the paper MCP tool, which
        # does not have the terminal's caps. Pipelines/compound commands
        # return shell output, with full bytes available inside the line.
        direct_paper = (len(words) == 3
                        and words[:2] == ["arxiv-latex", "get_paper_prompt"]
                        and words[2].startswith("{"))
        if not direct_paper:
            max_out, max_err, marker = terminal_output_limits()
            if len(stdout) > max_out:
                stdout = stdout[:max_out] + marker
            if len(stderr) > max_err:
                stderr = stderr[:max_err] + marker
    output = f"{stdout}\n{stderr}" if stdout and stderr else stdout or stderr
    for _ in re.findall(r"^[\w.-]+: Permission denied$", f"{stdout}\n{stderr}",
                        re.MULTILINE):
        output = output.removesuffix("\n") + f"\npolicy denied: {REFUSED_PATH}"
    return output


MANIFEST = ("task.json", )
# Relative to the repository root, not to `LOCAL`: the seeder is shared
# now, at `server/seed/`, next to the fakes it fills. It stays named here
# because which one rebuilds a dataset's fixtures is a property of the
# dataset -- a second one that needed its own would say so on this line.
SEEDER = ("server", "seed", "seed_task.py")
PROMPT = ("docs", "agent_system_prompt.md")
CONFIG = ("task_config.json", )
TOKENS = ("token_key_session.py", )
WORKSPACE = ("initial_workspace", )
EVALUATOR = ("evaluation", "main.py")

# Upstream's `local_tool_mappings`, by the name a task declares and the
# module it is imported from.
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


def root() -> Path:
    """The dataset's checkout, with its packages importable.

    Returns:
        Path: the checkout root.
    """
    found = Path(
        os.environ.get("TOOLATHLON_ROOT",
                       REPO_ROOT.joinpath(*CHECKOUT))).expanduser().resolve()
    if str(found) not in sys.path:
        sys.path.insert(0, str(found))
    return found


def gym() -> Path:
    """The GYM checkout, which carries the local MCP servers.

    Returns:
        Path: the checkout root.
    """
    return Path(
        os.environ.get("TOOLATHLON_GYM_ROOT",
                       REPO_ROOT.joinpath(*GYM))).expanduser().resolve()


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
    """The fixture manifest, which says what to build before a draw.

    Args:
        task (str): the task name.

    Returns:
        Path: the manifest, which most tasks do not have.
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

    Names, not tools: three of them expand to sets. `arms.build_local_tools`
    expands them through LOCAL_TOOLS the way upstream's own runner does.

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
    """The task's own `${token.*}` session, which several configs resolve.

    Args:
        task (str): the task name.

    Returns:
        Path: the file, which may not exist.
    """
    return task_dir(task).joinpath(*TOKENS)


def initial_workspace(task: str) -> Path:
    """The starting workspace both arms are given.

    Args:
        task (str): the task name.

    Returns:
        Path: the directory, which may not exist.
    """
    return task_dir(task).joinpath(*WORKSPACE)


def managed_workspace_paths(task: str) -> set[PurePosixPath]:
    """Initial-workspace paths owned by a task's fixture seeder.

    A script fixture whose id starts with ``workspace/`` declares that it
    manages that path during setup.  The distinction matters when the
    setup consumes its input: git-bug-hunt extracts ``files.tar.gz`` and
    deletes it, exactly as the original preprocess does.  Copying every
    initial file again after the script runs would undo that preprocess.

    Args:
        task (str): task directory name.

    Returns:
        set[PurePosixPath]: relative paths the generic copier must leave to
        the fixture seeder.
    """
    path = manifest(task)
    if not path.is_file():
        return set()
    fixtures = json.loads(path.read_text(encoding="utf-8"))["fixtures"]
    managed = set()
    for fixture in fixtures:
        fixture_id = fixture.get("id", "")
        if fixture.get(
                "kind") != "script" or not fixture_id.startswith("workspace/"):
            continue
        relative = PurePosixPath(fixture_id.removeprefix("workspace/"))
        if (not relative.parts or relative.is_absolute()
                or ".." in relative.parts):
            raise ValueError(f"invalid workspace fixture id {fixture_id!r}")
        managed.add(relative)
    return managed


def prepare_workspace(task: str, workspace: Path) -> None:
    """Apply workspace preprocessing omitted by the service seeders.

    apply-phd-email/preprocess/main.py extracts and removes files.tar.gz
    before the agent starts. Mail setup is already handled by seed_mail.
    """
    # These original preprocessors are filesystem-only. Run their pinned
    # source, including PDF selection, wrapper stripping and metadata cleanup.
    original_archives = {
        "paper-checker": "files.tar.gz",
        "reimbursement-form-filler": "bills/bills.tar.gz",
        "arrange-workspace": "initial_workspace.tar.gz",
        "courses-ta-hws": "files.tar.gz",
        "privacy-desensitization": "files.tar.gz",
    }
    if task in original_archives:
        source = subprocess.check_output([
            "git", "-C",
            str(root()), "show",
            f"HEAD:tasks/finalpool/{task}/preprocess/main.py"
        ],
                                         text=True)
        subprocess.run([
            sys.executable, "-c", source, "--agent_workspace",
            str(workspace)
        ],
                       check=True,
                       cwd=root())
        if (workspace / original_archives[task]).exists():
            raise RuntimeError(f"Original preprocessing failed for {task}")
        return
    archives = {
        "apply-phd-email": ["files.tar.gz"],
        "profile-update-online": ["files.tar.gz"],
        "latex-prompt-box": ["files.tar.gz", "codes.tar.gz"]
    }
    for filename in archives.get(task, []):
        archive = workspace / filename
        with tarfile.open(archive, "r:gz") as source:
            source.extractall(path=workspace, filter="data")
        archive.unlink()


# The tool-command CLIs by the server each stands in for: the key a task's
# yaml registers and the spec it points at. A CLI is named after its server,
# hyphens for underscores, which is how tests/parity.py maps it back.
TOOL_COMMANDS = (
    ('pdf-tools', 'pdf-tools', 'cli/toolathlon/documents.mjs:PDF'),
    ('excel', 'excel', 'cli/toolathlon/documents.mjs:EXCEL'),
    ('word', 'word', 'cli/toolathlon/documents.mjs:WORD'),
    ('pptx', 'pptx', 'cli/toolathlon/documents.mjs:PPTX'),
    ('google_calendar', 'google-calendar',
     'cli/toolathlon/google.mjs:CALENDAR'),
    ('google_sheet', 'google-sheet', 'cli/toolathlon/google.mjs:SHEETS'),
    ('emails', 'emails', 'cli/toolathlon/emails.mjs:EMAILS'),
    ('yahoo-finance', 'yahoo-finance',
     'cli/toolathlon/travel-video.mjs:YAHOO'),
    ('howtocook', 'howtocook', 'cli/toolathlon/travel-video.mjs:HOWTOCOOK'),
    ('memory', 'memory', 'cli/toolathlon/travel-video.mjs:MEMORY'),
    ('fetch', 'fetch', 'cli/toolathlon/research.mjs:WEB'),
    ('notion', 'notion', 'cli/toolathlon/travel-video.mjs:NOTION'),
    ('wandb', 'wandb', 'cli/toolathlon/travel-video.mjs:WANDB'),
    ('snowflake', 'snowflake', 'cli/toolathlon/travel-video.mjs:SNOWFLAKE'),
    ('google-cloud', 'google-cloud',
     'cli/toolathlon/travel-video.mjs:GOOGLE_CLOUD'),
)


@contextmanager
def services(task: str, workdir: str):
    """Start exact-handler CLIs for the original servers a task exposes."""
    sys.path.insert(0, str(REPO_ROOT))
    import yaml

    from server.seed.travel_video import (DOCUMENT_TOOLS, GOOGLE_TOOLS, TOOLS,
                                          serve_tools)
    config = local(task) / 'vfs/workspace.yaml'
    clis = yaml.safe_load(config.read_text()).get(
        'clis', {}) if config.is_file() else {}
    # A CLI is its server's transport when the yaml names it after the
    # server and points it at the tool-command spec; a builtin or a shim
    # under that name is not one.
    registered = [
        kind for kind, name, export in TOOL_COMMANDS
        if str(clis.get(name, {}).get('cli', '')).endswith(export)
    ]
    if not set(registered).issubset(needed_mcp_servers(task)):
        raise ValueError('Exact-handler CLI has no original MCP server for '
                         'this task')
    definitions = {**TOOLS, **GOOGLE_TOOLS, **DOCUMENT_TOOLS}
    variables = {kind: definitions[kind][2] for kind in registered}
    previous = {kind: os.environ.get(name) for kind, name in variables.items()}
    with ExitStack() as search_stack:
        # Research tasks already own this transport inside _services. Other
        # tasks that advertise upstream search need the same shared path.
        from server.seed.research import TASKS as research_tasks
        from server.seed.research import transport
        if 'web_search' in needed_local_tools(
                task) and task not in research_tasks:
            from server.seed.business import restore_environment
            search_stack.callback(
                restore_environment,
                {'SEARCH_CLI_URL': os.environ.get('SEARCH_CLI_URL')})
            url, _ = search_stack.enter_context(transport(task))
            os.environ['SEARCH_CLI_URL'] = url
        # Yahoo is live, as upstream reads it. Every SDK read -- the CLI's,
        # the MCP server's and the grader's -- goes through the one
        # recording transport, which the final batch starts in _services.
        from server.seed.final_batch import TASKS as final_tasks
        receipts = None
        if 'yahoo-finance' in registered and task not in final_tasks:
            from server.seed.business import restore_environment
            from server.seed.public_services import serve as public_services
            search_stack.callback(
                restore_environment,
                {'PUBLIC_SERVICE_URL': os.environ.get('PUBLIC_SERVICE_URL')})
            url, receipts = search_stack.enter_context(public_services())
            os.environ['PUBLIC_SERVICE_URL'] = url
        # A task whose Hub fixture has captured Dataset Viewer answers gets
        # them in front of the fake, for both arms, since both read the
        # endpoint `HF_MCP_URL` names. The live-endpoint task keeps the
        # live server and has no capture.
        from server.fakes import hub_viewer
        if 'huggingface' in needed_mcp_servers(task) and (
                hub_viewer.folder(task) / 'source.json').is_file():
            search_stack.enter_context(hub_viewer.serve(task))
        with _services(task, workdir) as record:
            if receipts is not None:
                # The run's record carries the recorder's receipts, under
                # the name the final batch gives them.
                record = {**(record or {}), 'public_api_requests': receipts}
            # A business, final-batch or research owner may already have
            # entered travel_video for a kind. Comparing the variable with
            # its value from before `_services` distinguishes an owned
            # endpoint from a stale ambient one without coupling this layer
            # to task lists.
            kinds = [
                kind for kind in registered
                if os.environ.get(variables[kind]) == previous[kind]
            ]
            with serve_tools(kinds, workdir, task) if kinds else nullcontext():
                yield record


@contextmanager
def _services(task: str, workdir: str):
    """Own per-arm services through execution and the upstream grader."""
    sys.path.insert(0, str(REPO_ROOT))
    from server.seed.research import TASKS as research_tasks
    from server.seed.research import serve as research
    if task in research_tasks:
        with research(task, workdir) as record:
            yield record
        return
    from server.seed.papers import TASKS as paper_tasks
    from server.seed.papers import serve as papers
    if task in paper_tasks:
        with papers(task, workdir) as record:
            yield record
        return
    from server.seed.business import TASKS, serve
    if task in TASKS:
        if task in {
                "woocommerce-update-cover", "filter-low-selling-products",
                "woocommerce-stock-alert", "update-material-inventory",
                "woocommerce-customer-survey", "woocommerce-product-recall"
        }:
            from server.seed.woocommerce_fixture import folder
            if not (folder(task) / "source.json").is_file():
                raise FileNotFoundError(
                    "The original WooCommerce fixture capture is missing")
        if task in {
                "canvas-new-students-notification", "canvas-art-manager",
                "canvas-homework-grader-python", "canvas-arrange-exam",
                "canvas-do-quiz", "canvas-submit-late-work"
        }:
            from server.seed.canvas_fixture import folder
            if not (folder(task) / "source.json").is_file():
                raise FileNotFoundError(
                    "The original Canvas fixture capture is missing")
        with serve(task, workdir) as record:
            # Here rather than in `serve`, which a capture also enters and
            # whose Drive it records: a restore checks the copy against the
            # template, so the capture has to keep it.
            if task in ("woocommerce-stock-alert",
                        "update-material-inventory"):
                from server.seed.business_sheets import remove_source
                remove_source(task)
            yield record
        return
    if "k8s" in needed_mcp_servers(task):
        sys.path.insert(0, str(REPO_ROOT))
        from server.seed.kubernetes import serve
        with ExitStack() as stack:
            if task == 'k8s-safety-audit':
                from server.seed.kubernetes_sheet import serve as sheet
                stack.enter_context(sheet())
            record = stack.enter_context(serve(task, workdir))
            yield record
        return
    if 'playwright_with_chunk' in needed_mcp_servers(task):
        from server.seed.browser import serve
        with serve(task, workdir) as record:
            yield record
        return
    if task == "experiments-recordings":
        from server.seed.experiments import serve
        with serve(local(task)) as base:
            yield base
        return
    if "wandb" not in needed_mcp_servers(task):
        yield
        return
    sys.path.insert(0, str(REPO_ROOT / "server/fakes"))
    from wandb_api import serve
    with serve(local(task)) as base:
        yield base


def close_commands(task: str) -> None:
    """Release native forwards before their owning MCP process exits."""
    if "k8s" in needed_mcp_servers(task):
        from server.seed.kubernetes import stop_forwards
        stop_forwards(os.environ['K8S_PROCESS_DIR'], os.environ['KUBECONFIG'])


def needs_stack(task: str) -> bool:
    """Standalone W&B tasks own their API fixture through services()."""
    from server.seed.research import TASKS as research_tasks
    if task in research_tasks and task != "verl-dataset":
        return False
    servers = set(needed_mcp_servers(task))
    if 'playwright_with_chunk' in servers and servers <= {
            'playwright_with_chunk', 'filesystem', 'memory', 'k8s', 'terminal'
    }:
        return False
    if task in {
            "experiments-recordings", "latex-prompt-box", "find-alita-paper"
    }:
        return False
    if servers & {"canvas", "woocommerce"} or servers == {"k8s", "filesystem"}:
        return False
    if servers == {"k8s", "terminal", "filesystem"}:
        return False
    return not ("wandb" in servers
                and servers <= {"wandb", "filesystem", "terminal", "excel"})


@cache
def conflict_groups() -> list[list[str]]:
    """Upstream's own list of tasks its parallel runner never overlaps.

    Read from the pinned commit rather than the working tree, as the runner
    profile is, and copied as it stands: `run_parallel.py` gives each group
    one lock, and so does this harness.

    Returns:
        list[list[str]]: the groups.
    """
    source = subprocess.check_output([
        "git", "-C",
        str(root()), "show", f"HEAD:{'/'.join(POOL)}/task_conflict.json"
    ],
                                     text=True)
    return json.loads(source)["conflict_groups"]


def holds(task: str) -> list[str]:
    """What a draw of this task holds on the host besides stack services.

    The fixed host ports its own services bind, which only one draw at a
    time can have and which cannot move because they are in what the model
    reads: Canvas and WooCommerce publish on the ports their URLs name
    (`server/seed/business.py`) and `meeting-assign` serves its site on 30137
    (`server/seed/final_batch.py`). And upstream's conflict groups.

    Args:
        task (str): the task name.

    Returns:
        list[str]: lock names.
    """
    servers = set(needed_mcp_servers(task))
    found = set()
    if "canvas" in servers:
        found.add("port-10001")
    if "woocommerce" in servers:
        found.add("port-10003")
    if task == "meeting-assign":
        found.add("port-30137")
    for group in conflict_groups():
        if task in group:
            found.add(f"conflict-{min(group)}")
    return sorted(found)


def run_provenance(task: str) -> dict:
    """Record input and code fingerprints outside the model prompt."""
    config = local(task) / "shared/wandb.json"
    runtime = {}
    runtime_kind = "kubernetes"
    from server.seed.business import TASKS as business_tasks
    from server.seed.papers import TASKS as paper_tasks
    if "k8s" in needed_mcp_servers(task):
        runtime = json.loads(Path(os.environ["K8S_SOURCE_RECORD"]).read_text())
        paths = [
            f"task/toolathlon/{task}/shared/task.md",
            f"task/toolathlon/{task}/task.json",
            f"task/toolathlon/{task}/vfs/workspace.yaml",
            f"task/toolathlon/{task}/vfs/VFS.md",
            f"task/toolathlon/{task}/vfs/SKILL.md",
            "vendor/kubernetes-mcp/package.json",
            "vendor/kubernetes-mcp/package-lock.json",
            "server/kubernetes-binaries.json",
            "vfs/kubernetes.mjs",
            "cli/toolathlon/kubectl.mjs",
            "cli/native.mjs",
            "server/kubectl.sh",
            "server/clients/kubernetes.mjs",
            "server/sandbox.py",
            "server/kubernetes_proxy.py",
            "server/kubernetes_template.py",
            "server/kubernetes-template.sh",
            "server/seed/kubernetes.py",
            "server/shared_workspace.py",
            "submodule/Toolathlon/uv.lock",
            "submodule/Toolathlon/pyproject.toml",
            "vendor/filesystem-mcp/package.json",
            "vendor/filesystem-mcp/package-lock.json",
            "server/mcp/setup_filesystem.py",
            "server/mcp/setup_kubernetes.py",
        ]
        paths += [
            str(path.relative_to(REPO_ROOT))
            for path in (local(task) / "shared").rglob("*")
            if path.is_file() and str(path.relative_to(REPO_ROOT)) not in paths
        ]
        paths += [
            "server/seed/kubernetes_sheet.py", "server/mcp/setup_helm.py",
            "server/helm.sh", "cli/toolathlon/helm.mjs",
            "cli/toolathlon/mysql.mjs"
        ]
        if task == "k8s-safety-audit":
            paths += [
                "vendor/google-sheets-mcp/pyproject.toml",
                "vendor/google-sheets-mcp/uv.lock",
                "vendor/google-sheets-mcp/source.json",
                "server/fakes/sheet_formats.py"
            ]
    elif task in business_tasks:
        runtime_kind = "business"
        runtime = json.loads(
            Path(os.environ["BUSINESS_SOURCE_RECORD"]).read_text())
        service = runtime["service"]
        paths = [
            str(path.relative_to(REPO_ROOT)) for path in local(task).rglob("*")
            if path.is_file()
        ]
        paths += [
            f"vendor/{service}-mcp/package.json",
            f"vendor/{service}-mcp/package-lock.json", f"vfs/{service}.mjs",
            f"cli/toolathlon/{service}.mjs", "vfs/service_api.mjs",
            "cli/toolathlon/service_api.mjs", "cli/toolathlon/tool.mjs",
            "cli/toolathlon/tool-client.mjs",
            "server/clients/original_tools.mjs", "server/seed/travel_video.py",
            f"vendor/{service}-mcp/source.json",
            f"vendor/{service}-mcp/tools.json",
            "server/clients/service_api.mjs",
            "server/clients/canvas_files.mjs", "server/seed/business.py",
            "server/seed/woocommerce_fixture.py",
            "server/business-sources.json", "server/sandbox.py",
            "server/mcp/npm_lock.py", "server/mcp/setup_commerce_canvas.py"
        ]
        if "mcp" in runtime:
            paths += [
                "server/seed/business_mcp.py", "server/seed/canvas_fixture.py",
                "submodule/Toolathlon/configs/mcp_servers/canvas.yaml"
            ]
        if "bigquery" in runtime:
            paths += [
                "server/seed/business_bigquery.py", "server/bq/token_stub.py",
                "redirect/bigquery/sitecustomize.py", "server/bq/proxy.py",
                "server/api/app.py", "server/api/logging_store.py",
                "docker/compose.yml", "server/clients/original_tools.py",
                "server/seed/travel_video.py",
                "cli/toolathlon/travel-video.mjs", "cli/toolathlon/tool.mjs",
                "cli/toolathlon/tool-client.mjs",
                "vendor/google-cloud-mcp/uv.lock",
                "vendor/google-cloud-mcp/pyproject.toml"
            ]
        if "sheets" in runtime:
            paths += [
                "server/seed/business_sheets.py", "server/fakes/gws_api.mjs",
                "server/fakes/sheet_formats.py", "docker/package.json",
                "docker/package-lock.json",
                "redirect/eval_shim/gws_redirect.py",
                "vendor/google-sheets-mcp/pyproject.toml",
                "vendor/google-sheets-mcp/uv.lock",
                "vendor/google-sheets-mcp/source.json"
            ]
        if "forms" in runtime:
            paths += [
                "server/seed/business_forms.py",
                "server/seed/business_sheets.py", "server/clients/forms.mjs",
                "server/fakes/forms_api.mjs", "redirect/forms/google_hook.mjs",
                "redirect/forms/sitecustomize.py",
                "server/fakes/sheet_formats.py", "docker/package.json",
                "docker/package-lock.json", "vendor/forms-mcp/package.json",
                "vendor/forms-mcp/package-lock.json",
                "vendor/forms-mcp/source.json", "cli/toolathlon/forms.mjs",
                "cli/toolathlon/tool.mjs", "cli/toolathlon/tool-client.mjs"
            ]
        if "mail" in runtime:
            paths += [
                "server/seed/business_mail.py", "server/mail-sources.json",
                "server/seed/seed_mail.py", "docker/compose.yml",
                "vendor/emails-mcp/pyproject.toml", "vendor/emails-mcp/uv.lock"
            ]
    elif task in paper_tasks:
        from server.seed.papers import TASKS, VENDORS, active
        runtime_kind = "papers"
        runtime = active()
        paths = [
            str(path.relative_to(REPO_ROOT)) for path in local(task).rglob("*")
            if path.is_file()
        ]
        paths += [
            "server/seed/papers.py", "server/clients/papers.py",
            "redirect/papers/sitecustomize.py", "cli/toolathlon/papers.mjs",
            "cli/toolathlon/tool.mjs", "cli/toolathlon/tool-client.mjs",
            "server/mcp/setup_papers_forms.py"
        ]
        for kind in TASKS[task]:
            paths += [
                "vendor/" + VENDORS[kind] + "/" + name
                for name in ("pyproject.toml", "uv.lock", "source.json")
            ]
        if 'arxiv_local' in TASKS[task]:
            paths += ["vendor/arxiv-local-mcp/original_wrapper.py"]
        if task == 'latex-prompt-box':
            runtime["shell"] = {
                "cwd": shell_cwd(task),
                "terminal_output_limits": terminal_output_limits(),
                "direct_paper_output": "original tool response",
            }
            paths += [
                "submodule/Toolathlon/configs/mcp_servers/terminal.yaml",
                ("submodule/toolathlon_gym/local_servers/cli-mcp-server/"
                 "src/cli_mcp_server/server.py"),
            ]
    elif config.is_file():
        fixture = json.loads(config.read_text())["fixture"]
        paths = [
            f"task/toolathlon/shared/fixtures/wandb/{fixture}.json" +
            (".gz" if fixture == "Guru" else ""),
            f"task/toolathlon/{task}/shared/task.md",
            f"task/toolathlon/{task}/shared/wandb.json",
            f"task/toolathlon/{task}/vfs/workspace.yaml",
            f"task/toolathlon/{task}/vfs/VFS.md",
            f"task/toolathlon/{task}/vfs/SKILL.md",
            "vendor/wandb-mcp/pyproject.toml",
            "vendor/wandb-mcp/uv.lock",
            "server/fakes/wandb_api.py",
            "server/fakes/wandb_api.mjs",
        ]
    else:
        paths = []
    if task == "experiments-recordings":
        paths += [
            str(path.relative_to(REPO_ROOT)) for path in local(task).rglob("*")
            if path.is_file() and str(path.relative_to(REPO_ROOT)) not in paths
        ]
        paths += [
            "server/seed/experiments.py", "server/fakes/wandb_files.mjs",
            "server/fakes/notion_api.mjs",
            "redirect/eval_shim/notion_redirect.py",
            "redirect/eval_shim/notion_sdk.py",
            "vendor/notion-mcp/package.json",
            "vendor/notion-mcp/package-lock.json"
        ]
    from server.seed.research import TASKS as research_tasks
    from server.seed.research import active as research_record
    if task in research_tasks:
        runtime = {'papers': runtime, **(research_record() or {})}
        runtime_kind = 'research'
        paths += [
            str(path.relative_to(REPO_ROOT)) for path in local(task).rglob('*')
            if path.is_file()
        ]
        paths += [
            'server/seed/research.py',
            'server/clients/fetch.mjs',
            'redirect/research/fetch_hook.mjs',
            'cli/toolathlon/research.mjs',
            'cli/toolathlon/tool.mjs',
            'cli/toolathlon/tool-client.mjs',
            'vendor/fetch-mcp/package.json',
            'vendor/fetch-mcp/package-lock.json',
            'submodule/Toolathlon/utils/aux_tools/web_search.py',
        ]
        if 'google_sheet' in needed_mcp_servers(task):
            paths += [
                'server/seed/research_sheets.py',
                'server/seed/business_sheets.py',
                'server/fakes/sheet_formats.py',
                'server/fakes/research_gws.mjs',
                'redirect/eval_shim/gws_redirect.py',
                'redirect/gws_sheets/sitecustomize.py',
                'vendor/google-sheets-mcp/uv.lock',
                'vendor/google-sheets-mcp/pyproject.toml',
                'vendor/google-sheets-mcp/source.json',
                'docker/sheets.Dockerfile',
                'docker/package.json',
                'docker/package-lock.json',
                'submodule/Toolathlon/configs/token_key_session_example.py',
                ('submodule/Toolathlon/utils/app_specific/'
                 'googlesheet/drive_helper.py'),
                'submodule/Toolathlon/configs/global_configs_example.py',
                'submodule/Toolathlon/utils/app_specific/google_oauth/ops.py',
            ]
        paths += [
            str(path.relative_to(REPO_ROOT))
            for path in task_dir(task).rglob('*') if path.is_file()
        ]
    from server.seed.final_batch import TASKS as final_tasks
    if task in final_tasks:
        paths += [
            'server/seed/final_batch.py',
            'server/seed/final_mail.py',
            'server/seed/public_services.py',
            'server/seed/travel_video.py',
            'server/clients/original_tools.mjs',
            'server/clients/original_tools.py',
            'server/clients/rail_http.mjs',
            'server/mcp/setup_travel_video.py',
            'cli/toolathlon/travel-video.mjs',
            'redirect/public_services/hook.mjs',
            'redirect/eval_shim/mail_redirect.py',
            'redirect/yahoo_capture/capture.py',
            'redirect/yahoo_capture/sitecustomize.py',
            'server/mcp/setup_memory.py',
            'server/mcp/setup_huggingface.py',
            'redirect/hub/sitecustomize.py',
            'redirect/eval_shim/hf_host.py',
            'server/mcp/setup_github.py',
            'vendor/mcp-remote/package.json',
            'vendor/mcp-remote/package-lock.json',
            'submodule/Toolathlon/local_binary/github-mcp-version.txt',
            'server/mail-sources.json',
            'server/fakes/notion_api.mjs',
            'redirect/eval_shim/notion_redirect.py',
        ]
        from server.seed.travel_video import TOOLS
        for name in needed_mcp_servers(task):
            if name in TOOLS:
                vendor = REPO_ROOT / 'vendor' / TOOLS[name][0]
                paths += [
                    str(path.relative_to(REPO_ROOT))
                    for path in vendor.iterdir()
                    if path.is_file() and path.suffix in ('.json', '.toml',
                                                          '.lock')
                ]
    task_root = local(task)
    paths += [
        str(path.relative_to(REPO_ROOT))
        for root in (task_root / 'shared', task_root / 'vfs') if root.is_dir()
        for path in root.rglob('*') if path.is_file()
    ]
    task_config = task_root / 'task.json'
    if task_config.is_file():
        paths.append(str(task_config.relative_to(REPO_ROOT)))
    paths += [
        "server/mcp/mcp_servers.py", "task/toolathlon/__init__.py",
        "task/toolathlon/task_paths.py", "agent/arms.py", "agent/workspace.py",
        "agent/run_agent.py", "uv.lock", "agent/context.py",
        "server/execution.py", "cli/processes.mjs", "agent/services.py",
        "agent/grading.py", "task/toolathlon/script/grade_task.py"
    ]
    if 'playwright_with_chunk' in needed_mcp_servers(task):
        paths += [
            str(path.relative_to(REPO_ROOT)) for path in local(task).rglob('*')
            if path.is_file()
        ]
        paths += [
            'vendor/browser-mcp/package.json',
            'vendor/browser-mcp/package-lock.json',
            'server/mcp/setup_browser.py', 'docker/browser.Dockerfile',
            'server/seed/browser.py', 'server/clients/browser.mjs',
            'cli/toolathlon/browser.mjs', 'cli/toolathlon/browser-client.mjs',
            'server/shared_workspace.py', 'submodule/Toolathlon/uv.lock',
            ('submodule/Toolathlon/configs/mcp_servers/'
             'playwright_with_chunk.yaml')
        ]
    if "filesystem" in needed_mcp_servers(task):
        paths += [
            "vendor/filesystem-mcp/package.json",
            "vendor/filesystem-mcp/package-lock.json",
            "server/mcp/setup_filesystem.py",
            "server/mcp/npm_lock.py",
            "submodule/Toolathlon/configs/mcp_servers/filesystem.yaml",
        ]
    if "google_sheet" in needed_mcp_servers(task):
        paths += ["vendor/google-sheets-mcp/uv.lock"]
    if "google-cloud" in needed_mcp_servers(task):
        paths += [
            "vendor/google-cloud-mcp/pyproject.toml",
            "vendor/google-cloud-mcp/uv.lock",
            "server/fakes/gcp.py",
            "server/fakes/stack.py",
            "server/seed/seed_bigquery.py",
            "server/bq/proxy.py",
            "server/bq/token_stub.py",
            "docker/compose.yml",
            "docker/Dockerfile",
            "docker/service.sh",
            "redirect/bigquery/sitecustomize.py",
            "redirect/cloud_logging/sitecustomize.py",
            "server/clients/cloud_logging.py",
            "server/clients/original_tools.py",
            "server/seed/travel_video.py",
            "cli/toolathlon/travel-video.mjs",
            "cli/toolathlon/tool.mjs",
            "cli/toolathlon/tool-client.mjs",
        ]
    if "snowflake" in needed_mcp_servers(task):
        paths += [
            "vendor/snowflake-mcp/pyproject.toml",
            "vendor/snowflake-mcp/uv.lock",
            "redirect/snowflake/snowflake/__init__.py",
            "redirect/snowflake/snowflake/connector/__init__.py",
            "redirect/snowflake/snowflake/snowpark/__init__.py",
            "server/clients/snowflake.py",
            "server/clients/original_tools.py",
            "server/seed/travel_video.py",
            "cli/toolathlon/travel-video.mjs",
            "cli/toolathlon/tool.mjs",
            "cli/toolathlon/tool-client.mjs",
        ]
    if "excel" in needed_mcp_servers(task):
        paths += [
            "submodule/Toolathlon/pyproject.toml",
            "submodule/Toolathlon/uv.lock",
            "submodule/Toolathlon/configs/mcp_servers/excel.yaml",
            "redirect/excel/sitecustomize.py",
        ]
    if "yahoo-finance" in needed_mcp_servers(task):
        paths += [
            "vendor/yahoo-finance-mcp/uv.lock",
            "vendor/yahoo-finance-mcp/source.json",
            "submodule/toolathlon_gym/local_servers/yahoo-finance-mcp/"
            "server.py", "redirect/yahoo_capture/capture.py",
            "redirect/yahoo_capture/sitecustomize.py",
            "server/seed/public_services.py",
            "server/clients/original_tools.py", "server/seed/travel_video.py",
            "cli/toolathlon/travel-video.mjs", "cli/toolathlon/tool.mjs",
            "cli/toolathlon/tool-client.mjs"
        ]
    if "emails" in needed_mcp_servers(task):
        paths += [
            "vendor/emails-mcp/pyproject.toml",
            "vendor/emails-mcp/uv.lock",
            "vendor/emails-mcp/source.json",
            "vendor/emails-mcp/tools.json",
            "submodule/Toolathlon/configs/mcp_servers/emails.yaml",
            "server/mcp/setup_email.py",
            "server/clients/original_tools.py",
            "server/seed/travel_video.py",
            "cli/toolathlon/emails.mjs",
            "cli/toolathlon/tool.mjs",
            "cli/toolathlon/tool-client.mjs",
        ]
    if "howtocook" in needed_mcp_servers(task):
        paths += [
            "vendor/howtocook-mcp/package.json",
            "vendor/howtocook-mcp/package-lock.json",
            "server/mcp/setup_howtocook.py",
            "server/clients/original_tools.mjs",
            "server/seed/travel_video.py",
            "cli/toolathlon/travel-video.mjs",
            "cli/toolathlon/tool.mjs",
            "cli/toolathlon/tool-client.mjs",
        ]
    if "notion" in needed_mcp_servers(task):
        paths += [
            "vendor/notion-mcp/package.json",
            "vendor/notion-mcp/package-lock.json",
            "server/mcp/setup_notion.py",
            "server/fakes/notion_api.mjs",
            "server/clients/original_tools.py",
            "server/seed/travel_video.py",
            "cli/toolathlon/travel-video.mjs",
            "cli/toolathlon/tool.mjs",
            "cli/toolathlon/tool-client.mjs",
        ]
    if "fetch" in needed_mcp_servers(task) and task not in research_tasks:
        paths += [
            "vendor/fetch-mcp/package.json",
            "vendor/fetch-mcp/package-lock.json",
            "server/mcp/setup_fetch.py",
            "redirect/fetch/fetch_hook.mjs",
            "server/clients/original_tools.mjs",
            "server/seed/travel_video.py",
            "cli/toolathlon/research.mjs",
            "cli/toolathlon/tool.mjs",
            "cli/toolathlon/tool-client.mjs",
        ]
    revisions = {}
    for path in (".", "submodule/Toolathlon", "submodule/toolathlon_gym",
                 "submodule/mirage"):
        checkout = REPO_ROOT / path
        revisions[path] = {
            "revision":
            subprocess.check_output(["git", "rev-parse", "HEAD"],
                                    cwd=checkout,
                                    text=True).strip(),
            "dirty":
            subprocess.run(["git", "diff", "--quiet", "HEAD"],
                           cwd=checkout).returncode != 0
        }
    from server.seed.browser import active as local_browser
    from server.shared_workspace import active
    browser_record = (active().browser_record if active() else local_browser())
    from server.execution import container
    native_execution = ({
        "filesystem_boundary": "e2b",
        "user": "user"
    } if active() else {
        "filesystem_boundary": "upstream-image",
        "image": container()["image"],
        "network": "host",
        "user": "root"
    } if container() else {
        "filesystem_boundary":
        "seatbelt" if sys.platform == "darwin" else "bubblewrap"
    })
    paths = list(dict.fromkeys(paths))
    return {
        "git": revisions,
        "native_execution": native_execution,
        **({
            'browser': browser_record
        } if browser_record else {}),
        **({
            runtime_kind: runtime
        } if runtime else {}), "sha256": {
            path: hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest()
            for path in paths
        }
    }


def evaluator(task: str) -> Path:
    """The evaluator that grades a run.

    Args:
        task (str): the task name.

    Returns:
        Path: the evaluator, which may not exist.
    """
    return task_dir(task).joinpath(*EVALUATOR)


def evaluator_argv(task: str) -> tuple[list[str], Path]:
    """How this dataset's evaluator has to be invoked, and from where.

    Not a path: upstream's evaluators use relative imports and are run as
    modules from the checkout (`utils/data_structures/task_config.py` runs
    `uv run -m ...`), in the checkout's own virtualenv, because it pins an
    `openai-agents` this repo cannot use.

    Args:
        task (str): the task name.

    Returns:
        tuple: the argv prefix, and the working directory to run it in.
    """
    module = ".".join((*POOL, task, *EVALUATOR)).removesuffix(".main.py")
    return ["uv", "run", "-m", f"{module}.main"], root()
