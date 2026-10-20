import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "task"))

import dataset  # noqa: E402
import services  # noqa: E402

MAX_TOOL_OUTPUT = services.MAX_TOOL_OUTPUT
REPO_ROOT = services.REPO_ROOT
web_fixture = services.web_fixture
yf_dsn = services.yf_dsn


# Resolved when a builder asks, not when this module is imported. `dataset.gym`
# and `dataset.root` are Toolathlon's own -- two checkouts named after that
# benchmark -- and binding them at import time asks every dataset for them,
# including the ones that have neither. Only Toolathlon's builders below call
# these, so laziness is the whole fix.
def gym_path() -> Path:
    """Toolathlon-GYM's checkout.

    Returns:
        Path: the checkout root.
    """
    return dataset.gym()


def toolathlon_path() -> Path:
    """Toolathlon's checkout.

    Returns:
        Path: the checkout root.
    """
    return dataset.root()


@dataclass(frozen=True)
class Launch:
    """Everything a server builder is allowed to depend on.

    Attributes:
        task_dir (Path): the task directory, whose name is the Toolathlon
            task and whose `shared/` holds its per-service manifests.
        workdir (str): the agent workspace, absolute.
        sheets (str): "upstream" or "gym"; only google_sheet reads it.
    """

    task_dir: Path
    workdir: str
    sheets: str = "upstream"

    @property
    def vendored(self) -> Path:
        """Toolathlon-GYM's `local_servers`, which several servers run from.

        Returns:
            Path: the directory.
        """
        return gym_path() / "local_servers"


def needed_mcp_servers(task_dir: Path) -> list[str]:
    """Read the server list Toolathlon declares for this task.

    The task's own task_config.json is the source of truth, so a new task
    needs no wiring here beyond a builder for any server it is the first
    to use.

    Args:
        task_dir (Path): task directory; its name is the Toolathlon task.
    """
    return dataset.needed_mcp_servers(task_dir.name)


def needed_local_tools(task_dir: Path) -> list[str]:
    """Read the local-tool list Toolathlon declares for this task.

    The other half of the same declaration, and read the same way. It
    varies far more than the server list does: of the forty-six tasks
    measured here, only twenty-eight are given `python_execute` and two
    `web_search`, so a surface built from a fixed list rather than from
    this one hands eighteen tasks an interpreter upstream withholds.

    Args:
        task_dir (Path): task directory; its name is the Toolathlon task.
    """
    return dataset.needed_local_tools(task_dir.name)


# --------------------------------------------------------------------------
# per-task settings read out of upstream's own files, never restated here


def notion_config(task_dir: Path) -> dict:
    """Read the task's Notion identity, shared by both arms.

    `shared/notion.json` sits beside the fixture and names the two values the
    arms have to agree on: the bearer token, which mirage's fake treats as the
    workspace id, and the page the task is about.

    Args:
        task_dir (Path): task directory.

    Returns:
        dict: {"workspace", "page_id", "page_title"}.
    """
    return json.loads((task_dir / "shared" / "notion.json").read_text())


def notion_workspace(task_dir: Path) -> str:
    """The bearer token that scopes both arms to this task's workspace.

    Args:
        task_dir (Path): task directory.
    """
    return str(notion_config(task_dir)["workspace"])


def notion_page_id(task_dir: Path) -> str:
    """The page the task is about, standing in for upstream's duplicated page.

    Args:
        task_dir (Path): task directory.
    """
    return str(notion_config(task_dir)["page_id"])


def snowflake_database(task_dir: Path) -> str:
    """The one Snowflake database a task is allowed to touch.

    Each snowflake task overrides `snowflake_op_allowed_databases` in its
    own `token_key_session.py`, and that name is both what the server is
    launched with and what this repo creates in Postgres. Read out of
    upstream's file rather than restated here, so the two cannot drift.

    Args:
        task_dir (Path): the task directory.

    Returns:
        str: the database name, upper case as Snowflake spells it.

    Raises:
        FileNotFoundError: the task declares no database.
    """
    tokens = dataset.tokens(task_dir.name)
    found = re.search(r"snowflake_op_allowed_databases\s*=\s*[\"']([^\"']+)",
                      tokens.read_text() if tokens.is_file() else "")
    if not found:
        raise FileNotFoundError(
            f"no snowflake_op_allowed_databases in {tokens}")
    return found.group(1)


def gcp_allowed(task_dir: Path) -> dict[str, str]:
    """The four resource gates one google-cloud task is launched with.

    Each task overrides some of `google_cloud_allowed_{buckets,
    bigquery_datasets,log_buckets,instances}` in its own
    `token_key_session.py` and inherits the rest from
    `configs/token_key_session_example.py`, where every one defaults to the
    string `"null"`. Read out of upstream's files rather than restated here,
    so the two cannot drift -- and the defaults matter as much as the
    overrides, because `"null"` is how a task says it never touches Cloud
    Storage or Cloud Logging at all.

    The file is *executed*, the way `utils/data_structures/task_config.py`
    executes it, rather than pattern-matched. Reading it with a regex worked
    for as long as every ported task wrote a literal, and machine-operating
    is the first that does not: its bucket carries a uuid, so the name is
    read at import time out of `groundtruth_workspace/bucket_name.txt`. A
    regex sees no literal there, falls through to `"null"`, and the MCP arm
    is launched with Cloud Storage switched off -- which is not a smaller
    surface, it is an arm that cannot do the task.

    Args:
        task_dir (Path): the task directory.

    Returns:
        dict[str, str]: the four values, keyed by the flag's suffix.
    """
    import importlib.util

    names = ("buckets", "bigquery_datasets", "log_buckets", "instances")
    tokens = dataset.tokens(task_dir.name)
    if not tokens.is_file():
        return {name: "null" for name in names}
    spec = importlib.util.spec_from_file_location("token_key_session", tokens)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    session = module.all_token_key_session
    return {
        name: str(session.get(f"google_cloud_allowed_{name}") or "null")
        for name in names
    }


def github_access(task_dir: Path) -> dict[str, str]:
    """The two access knobs Toolathlon sets per task, read from its own file.

    These are not cosmetic. The global `configs/token_key_session.py` defaults
    to `github_read_only = "1"`, which would ban every write, and a task that
    writes overrides it in its own `token_key_session.py`. The other knob
    decides the tool surface as well as the permission: with
    GITHUB_ALLOWED_REPOS set, the fork's `create_repository` refuses outright
    ("repository creation is disabled when GITHUB_ALLOWED_REPOS is
    configured"), so a task that names its repositories is one where the
    agent has to fork and rename rather than create.

    Read by regex rather than by importing the module, which would need
    `addict` and Toolathlon's package layout on the path.

    Args:
        task_dir (Path): task directory.

    Returns:
        dict[str, str]: the environment for the github MCP server.
    """
    upstream = dataset.tokens(task_dir.name)
    values = {"github_allowed_repos": "null", "github_read_only": "1"}
    if upstream.exists():
        text = upstream.read_text()
        for key in values:
            found = re.search(rf'{key}\s*=\s*"([^"]*)"', text)
            if found:
                values[key] = found.group(1)
    return {
        # Upstream spells "no restriction" as the string "null".
        "GITHUB_ALLOWED_REPOS":
        "" if values["github_allowed_repos"] == "null" else
        values["github_allowed_repos"],
        "GITHUB_READ_ONLY":
        ""
        if values["github_read_only"] == "0" else values["github_read_only"],
    }


def yf_pg_env() -> dict[str, str]:
    """Spell the fixture DSN the way the snowflake shim expects to read it.

    The shim takes five PG_* variables rather than a URL, so the one DSN
    this repo configures has to be taken apart for it.

    Returns:
        dict[str, str]: PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD.
    """
    parsed = urlparse(yf_dsn())
    return {
        "PG_HOST": parsed.hostname or "localhost",
        "PG_PORT": str(parsed.port or 5432),
        "PG_DATABASE": (parsed.path or "/").lstrip("/") or "postgres",
        "PG_USER": parsed.username or "postgres",
        "PG_PASSWORD": parsed.password or "",
    }


def gws_calendar_env() -> dict[str, str]:
    """What the calendar MCP server needs to reach the mock instead of Google.

    Three variables and no code, which is why the dataset's own
    `script/grade_task.py` can set the same ones for the evaluator: it
    spawns the server from Toolathlon's
    own yaml, where there is no place to put a `--import`, so the hook goes
    in through NODE_OPTIONS there.

    Returns:
        dict[str, str]: GWS_MOCK_URL and the two OAuth paths.
    """
    fake = REPO_ROOT / "redirect" / "gws_calendar"
    return {
        "GWS_MOCK_URL": os.environ.get("GWS_URL", "http://127.0.0.1:19999"),
        "CALENDAR_OAUTH_PATH": str(fake / "gcp-oauth.keys.json"),
        "CALENDAR_CREDENTIALS_PATH": str(fake / "credentials.json"),
    }


def vendored(path: Path, setup: str) -> Path:
    """Check a server this repo vendors is actually installed.

    Every `bin/setup_*_mcp.py` pins a server rather than letting `uvx` or
    `npx` resolve latest at run time, because the version decides the tool
    surface and the tool surface is half of what the MCP arm is measured on.
    The cost is that a fresh checkout has none of them, so each builder says
    which command installs the one it wants.

    Args:
        path (Path): the executable or entry point.
        setup (str): the command that produces it.

    Returns:
        Path: the same path, resolved.

    Raises:
        FileNotFoundError: it is not installed.
    """
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"no vendored MCP server at {resolved}; "
                                f"run `{setup}`")
    return resolved


# --------------------------------------------------------------------------
# the builders, one per server, in the order Toolathlon's configs list them


def filesystem(at: Launch) -> dict:
    """Toolathlon's locked reference filesystem server.

    Upstream invokes this package through npx, but its repository lock fixes
    the complete dependency tree. setup_filesystem.py derives that exact
    closure instead of launching whichever release npx resolves later. The
    original workspace argument and server code are unchanged.

    In upstream's image, npx run from /workspace/dumps/workspace resolves
    the copy under /workspace/node_modules (2025.7.1, as locked here). This
    workspace is not under /workspace, where npx would fetch a release
    instead, so the container runs that copy's entry by path, from the
    workspace, as npx would.
    """
    from server.execution import contained, container
    from server.mcp.setup_filesystem import (ENTRY, verify_install,
                                             verify_source)
    from server.shared_workspace import active
    if container():
        return contained([
            'node', '/workspace/node_modules/@modelcontextprotocol/'
            'server-filesystem/dist/index.js', at.workdir
        ])
    if remote := active():
        verify_source()
        # Transport divergence: the same locked package tree runs in E2B;
        # only the workspace path changes to the shared FUSE mount.
        return remote.launch([
            'node',
            ('/opt/filesystem/node_modules/@modelcontextprotocol/'
             'server-filesystem/dist/index.js'), '/work'
        ])
    cli = vendored(ENTRY, "uv run python server/mcp/setup_filesystem.py")
    verify_source()
    verify_install()
    return {
        "command": "node",
        "args": [str(cli), at.workdir],
        "cwd": at.workdir,
    }


def terminal(at: Launch) -> dict:
    """lockon-n's cli-mcp-server fork, with upstream's own caps.

    The full upstream allowlist is model-visible. Native runs launch
    upstream's own `uvx` line in upstream's task image
    (server/execution.py's IMAGE), with its network, its GNU tools and the
    fork's Python 3.12 as `python`. Divergences: the workspace is the run's
    host path, mounted at that path rather than /workspace/dumps/workspace;
    the image is amd64-only, so on an arm64 host it runs emulated, about
    twice as slow; and the Hub redirect (HF_ENDPOINT) is passed in.

    Kubernetes tasks outside E2B keep the host launch, whose commands are
    denied public egress via macOS Seatbelt or checksum-pinned Linux
    Sandlock (Landlock and supervised seccomp IP checks). Mirage's builtin
    HTTP uses its existing proxy hook (cli/fixture-network.mjs) with the
    same loopback scope.
    """
    from server.shared_workspace import active
    if remote := active():
        import yaml

        # Browser tasks retain upstream's live network commands. The same
        # fork runs in E2B with the original Python dependency closure.
        config = yaml.safe_load(upstream_config('terminal'))['params']
        env = {
            key: value.replace('${agent_workspace}', '/work')
            for key, value in config['env'].items()
        }
        env['PYTHONPATH'] = '/opt/terminal'
        return remote.launch([
            '/opt/agent-python/.venv/bin/python', '-c',
            'from cli_mcp_server import main; main()'
        ], env)
    import yaml

    from server.execution import contained, container, model_environment
    config = yaml.safe_load(upstream_config("terminal"))["params"]
    # Only the transport and fixture boundary differ. Keeping the complete
    # allowlist preserves the fork's model-visible run_command description.
    env = {
        key: value.replace("${agent_workspace}", at.workdir)
        for key, value in config["env"].items()
    }
    if container():
        # Upstream's own line in upstream's image: its `uvx` runs the fork
        # the image installed (lockon-n@da1dcb51, identical source) and puts
        # that tool's Python 3.12 first on PATH, which is the terminal's
        # `python`. The Hub redirect is passed as to the model's Python.
        return contained(
            [config["command"], *config["args"]], {
                **env,
                **{
                    key: os.environ[key]
                    for key in ('HF_ENDPOINT', 'HF_TOKEN') if key in os.environ
                }
            })
    # The model's commands run in this server's environment, so it gets its
    # own `env` block and what model-run code may see -- not every other
    # server's credentials, which `env` would print. It starts in the
    # workspace, as upstream's does: `--project`, unlike `--directory`,
    # leaves `cwd` where it is.
    return {
        "command":
        "uv",
        "args": [
            "--project",
            str(at.vendored / "cli-mcp-server"), "run", "cli-mcp-server"
        ],
        "env": {
            **model_environment(),
            **env
        },
        "cwd":
        at.workdir,
    }


def git(at: Launch) -> dict:
    """The unmodified upstream git server.

    Toolathlon runs it as-is (configs/mcp_servers/git.yaml: "Toolathlon
    Version: The same").
    """
    return {
        "command": "uv",
        "args": ["run", "-m", "mcp_server_git"],
        "cwd": str(at.vendored / "servers" / "src" / "git"),
    }


def emails(at: Launch) -> dict:
    """Points at whatever IMAP/SMTP the task's emails_config.json names.

    Toolathlon runs poste.io on 1143/1587
    (global_preparation/deploy_containers.sh); this repo runs GreenMail on
    the same ports, and the config file is what decides.

    Divergence: upstream's uvx resolves at launch; our locked project fixes
    emails-mcp 0.1.12 and its full dependency tree, including the pre-2 MCP
    SDK whose FastMCP API this server imports. Args and server code match.

    Business tasks run the same mail fixture inside their owned E2B sandbox.
    Only the local IMAP/SMTP ports in the config change to reach its tunnels;
    the original task config is used by the remote seeder and grader.
    """
    from server.mcp.setup_email import verify
    verify()
    config = at.task_dir / "shared" / "emails_config.json"
    if os.environ.get("BUSINESS_TASK") == at.task_dir.name:
        config = Path(os.environ["BUSINESS_EMAIL_CONFIG"])
    return {
        "command":
        "uv",
        "args": [
            "run",
            "--locked",
            "--project",
            str(REPO_ROOT / "vendor" / "emails-mcp"),
            "emails-mcp",
            "--attachment_download_path",
            f"{at.workdir}/emails_download",
            "--attachment_upload_path",
            at.workdir,
            "--email_export_path",
            f"{at.workdir}/emails_export",
            "--config_file",
            str(config),
        ],
    }


def excel(at: Launch) -> dict:
    """The Excel server from Toolathlon's own locked Python project.

    Upstream's bare `uv run excel-mcp-server stdio` is resolved here through
    its committed uv.lock, which fixes excel-mcp-server 0.1.4 and the Python
    dependency tree that serialises its schemas.

    Divergence: a logging hook puts excel-mcp.log in the run's writable
    scratch instead of the read-only package directory. The original
    entry point, arguments, tools and schemas are unchanged.

    The Excel CLI reuses this launch. Its transport maps only file arguments
    and status paths between /workspace and the confined backing directory.
    """
    from server.shared_workspace import active
    if remote := active():
        return remote.launch(
            ["/opt/agent-python/.venv/bin/excel-mcp-server", "stdio"],
            {"PYTHONPATH": "/opt/excel-redirect"})
    return {
        "command": "uv",
        "args": ["run", "--locked", "excel-mcp-server", "stdio"],
        "env": {
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT / 'redirect/excel'),
            # Selecting the project through env lets server.execution expose
            # only its lock, manifest and virtualenv, not Toolathlon's task
            # and ground-truth directories beside them.
            "UV_PROJECT": str(toolathlon_path()),
        },
        "cwd": at.workdir,
    }


def yahoo_finance(at: Launch) -> dict:
    """The original Yahoo server, reading the original SDK live.

    Upstream reads Yahoo live on every task, so both arms do too, and
    nothing a run reads is kept: the CLI's reads, this server's and the
    grader's all go through the one recording transport. The Gym server.py
    is byte-identical to the original Dockerfile's Yahoo commit
    469103ba1464486cb7b8bd2c1f6355f42ca64a5b; setup.final_lineage checks its
    hash.

    Divergence: the full existing environment, including the pandas and
    psycopg2 extras, is captured in vendor/yahoo-finance-mcp/uv.lock. The
    pinned GYM server source and tool schemas remain unchanged.
    """
    from server.seed.travel_video import parameters
    return parameters('yahoo-finance', at.workdir)


def kubernetes(at: Launch) -> dict:
    """Original fork and dependencies from Toolathlon's package-lock.json.

    Divergences: node launches the locked entry instead of resolving with
    npx. Both arms receive a credential-free loopback kubeconfig; a harness
    kubectl proxy owns authentication and routes TLS through a tunnel to E2B.
    Its HTTP loopback config opts into client-node's skipTLSVerify requirement;
    the private upstream connection continues to verify TLS.
    kubectl matches Kind's Kubernetes version; upstream downloads a moving
    stable client. Server code, schemas and application args are unchanged.
    """
    import yaml
    config = yaml.safe_load(upstream_config("k8s"))
    if (config["params"]["command"] != "npx"
            or config["params"]["args"] != ["-y", "mcp-server-kubernetes"]):
        raise RuntimeError("Upstream Kubernetes launch changed")
    from server.shared_workspace import active
    if remote := active():
        # MySQL transport divergence: locked original server and kubectl
        # execute in E2B, with its original authenticated kubeconfig.
        # SSH preserves stdio and port-forward lifetime through grading.
        # Python uses the original locked environment; its local tool
        # handler and model-visible schema remain unchanged.
        return remote.launch([
            'node',
            '/opt/k8s-mcp/node_modules/mcp-server-kubernetes/dist/index.js'
        ])
    folder = REPO_ROOT / "vendor/kubernetes-mcp"
    entry = vendored(
        folder / "node_modules/mcp-server-kubernetes/dist/index.js",
        "uv run python server/mcp/setup_kubernetes.py")
    return {
        "command": "node",
        "args": [str(entry)],
        "cwd": at.workdir,
        "env": {
            **os.environ, "KUBECONFIG_PATH": os.environ["KUBECONFIG"]
        }
    }


def canvas(at: Launch) -> dict:
    """Original Canvas fork and dependency closure from the upstream lock.

    Node launches the pinned entry instead of npx. The original local ports
    tunnel to a fresh E2B container. canvas-art-quiz uses its committed
    other_key.py teacher identity, matching its seeder and grader; upstream
    otherwise falls back to an unrelated global account for its MCP server.
    Tool code, descriptions, schemas and API data are unchanged.

    The VFS CLI calls the same registered handlers through a local HTTP
    transport, without an MCP client. It removes only the canvas_ command
    prefix and translates upload paths under /work to the shared workspace.
    Binary upload/download helpers retain workspace stdin/stdout support.
    Mount traversal still uses the REST client and lists complete directories.
    DVC records tools.json and hashes of the installed original implementation;
    both arms verify those hashes before launching.

    The notification and homework preprocessors also invoke MCP in E2B.
    business_mcp installs this same lock there and replaces only npx with
    the installed Node entry. The original timeout and environment remain.
    """
    from server.mcp.setup_commerce_canvas import verify
    verify('canvas')
    import yaml
    config = yaml.safe_load(upstream_config("canvas"))
    if config["params"]["args"] != ["-y", "canvas-mcp-server"]:
        raise RuntimeError("Upstream Canvas launch changed")
    entry = vendored(
        REPO_ROOT /
        "vendor/canvas-mcp/node_modules/canvas-mcp-server/build/index.js",
        "uv run python -m server.mcp.setup_commerce_canvas")
    return {
        "command": "node",
        "args": [str(entry)],
        "cwd": at.workdir,
        "env": {
            "CANVAS_API_TOKEN": os.environ["CANVAS_API_TOKEN"],
            "CANVAS_DOMAIN": os.environ["CANVAS_DOMAIN"],
            "NODE_TLS_REJECT_UNAUTHORIZED": "0"
        }
    }


def woocommerce(at: Launch) -> dict:
    """Original WooCommerce dependency tree, aimed at the fixture.

    The VFS CLI calls its registered handlers without an MCP client, removing
    only the woo_ prefix. Pagination and text rendering remain upstream's.
    The mount traverses REST collections separately. Both arms verify the
    DVC-captured tool catalog and implementation hashes before launching.
    """
    from server.mcp.setup_commerce_canvas import verify
    verify('woocommerce')
    import yaml
    config = yaml.safe_load(upstream_config("woocommerce"))
    if config["params"]["args"] != ["-y", "@lockon0927/woocommerce-mcp"]:
        raise RuntimeError("Upstream WooCommerce launch changed")
    entry = vendored(
        REPO_ROOT / "vendor/woocommerce-mcp/node_modules/@lockon0927/"
        "woocommerce-mcp/dist/index.js",
        "uv run python -m server.mcp.setup_commerce_canvas")
    return {
        "command": "node",
        "args": [str(entry)],
        "cwd": at.workdir,
        "env": {
            key: os.environ[key]
            for key in ("WORDPRESS_SITE_URL", "WOOCOMMERCE_CONSUMER_KEY",
                        "WOOCOMMERCE_CONSUMER_SECRET")
        }
    }


def wandb(at: Launch) -> dict:
    """Toolathlon's named W&B fork, with its original locked dependencies.

    Divergence: the YAML's bare uvx package is no longer available on PyPI.
    The named lockon-n fork is pinned in vendor/wandb-mcp/uv.lock; its
    dependency versions are retained from that commit's own uv.lock.
    WANDB_BASE_URL redirects the unmodified server/SDK to Mirage's captured
    API fixture. Public run data is frozen; authentication is synthetic.
    server/fakes/wandb_api.mjs restores observed page sizes, run ordering,
    metadata and sampled history over Mirage's integration mock. Uncaptured
    downsampling or one-step windows fail rather than being approximated.
    Captures verify that x_axis/start/end/stride options are ignored by W&B.
    Other GraphQL reads use the pinned mock's schema and supported filters.
    The mock covers experiment reads, not Weave, support bot or report writes.
    """
    import yaml
    from arms import NO_NETWORK
    config = yaml.safe_load(upstream_config("wandb"))
    args = config["params"]["args"]
    if config["params"]["command"] != "uvx" or args != [
            "--from", "wandb-mcp-server", "wandb_mcp_server"
    ]:
        raise RuntimeError("Upstream W&B launch changed; review its lineage")
    if not os.environ.get("WANDB_BASE_URL",
                          "").startswith("http://127.0.0.1:"):
        raise RuntimeError("W&B fixture must be opened before its MCP server")
    return {
        "command":
        "uv",
        "args": [
            "run", "--locked", "--project",
            str(REPO_ROOT / "vendor/wandb-mcp"), args[-1]
        ],
        "cwd":
        at.workdir,
        "env": {
            **os.environ,
            **NO_NETWORK
        },
    }


def office(name: str):
    """Build the word or pptx builder.

    Upstream runs `uvx --from <pypi name>`, which resolves latest at
    runtime, in the agent workspace; the vendored copies are the same
    servers pinned. `--project` names the copy because the workspace is not
    a project; `--directory` would also move the server into the copy, where
    a relative name finds the copy's own files instead of the workspace's.

    The word and pptx CLIs reuse this launch. Their transport maps only file
    arguments and status paths between the workspace mount and the confined
    backing directory; document text is returned unchanged.

    Args:
        name (str): "word" or "pptx".

    Returns:
        A builder for that server.
    """
    package, entry = {
        "word": ("Office-Word-MCP-Server", "word_mcp_server"),
        "pptx": ("Office-PowerPoint-MCP-Server", "ppt_mcp_server"),
    }[name]

    def build(at: Launch) -> dict:
        return {
            "command": "uv",
            "args": ["--project",
                     str(at.vendored / package), "run", entry],
            "cwd": at.workdir,
        }

    return build


def snowflake(at: Launch) -> dict:
    """The snowflake server, answering out of the fixture Postgres.

    Upstream runs `uvx mcp_snowflake_server` against a paid Snowflake
    account. server/mcp/setup_snowflake.py vendors the fork its config names --
    fourteen tools, not PyPI's eight -- and installs it without the two
    cloud clients; redirect/snowflake takes their place and answers out of
    the fixture Postgres. Every flag below is upstream's, including the ones
    that describe a tenancy nobody connects to, because they are what the
    server's own argument parsing expects to find.

    `--database` and `--schema` are the session's current database and
    schema, which upstream's `token_key_session.py` leaves at its own
    defaults, `SNOWFLAKE` and `PUBLIC`, for every task: a task overrides only
    `snowflake_op_allowed_databases`. So a name that is not fully qualified
    resolves in `SNOWFLAKE` there, and does here too, rather than in the
    task's database.

    The shared dialect shim translates SYSDATE() to UTC and the second,
    minute, hour and day forms of DATEDIFF to boundary differences. DATEADD
    hour and day become interval arithmetic. Other DATEDIFF and DATEADD units
    are not emulated.

    One of upstream's flags is *not* below, and its absence is deliberate:
    `--private_key_path`. `db_client._init_database` opens that path itself,
    before `redirect/snowflake` is reached, so passing upstream's value
    points it at a key file that does not exist here and the connection
    fails outright. Dropping it costs nothing the model can see -- the
    server advertises the same fourteen tools with identical descriptions
    and schemas either way, checked by listing both.
    """
    cli = vendored(
        REPO_ROOT / "vendor" / "snowflake-mcp" / ".venv" / "bin" /
        "mcp_snowflake_server", "uv run python server/mcp/setup_snowflake.py")
    database = snowflake_database(at.task_dir)
    return {
        "command":
        str(cli),
        "args": [
            # Still the old repository name, and left that way: this is the
            # tenancy the fake answers as, not a reference to this repo.
            "--account",
            "toolathlon-vfs",
            "--warehouse",
            "COMPUTE_WH",
            "--user",
            "eigent",
            "--role",
            "ACCOUNTADMIN",
            "--database",
            "SNOWFLAKE",
            "--schema",
            "PUBLIC",
            "--allowed_databases",
            database,
            "--allow_write",
            "--exclude-json-results",
        ],
        "env": {
            **os.environ,
            **yf_pg_env(),
            "PYTHONPATH": str(REPO_ROOT / "redirect" / "snowflake"),
        },
        "cwd":
        at.workdir,
    }


def google_cloud(at: Launch) -> dict:
    """One server over three services, each faked a different way.

    Upstream runs `uvx google-cloud-mcp` against a live GCP project.
    server/mcp/setup_google_cloud.py vendors the repository that config names,
    pinned -- PyPI 1.0.0 gates resources by exact set membership and
    ab-testing needs the '*' the pinned commit adds. Both are the same 39
    tools, so the surface being measured is the same either way.

    BigQuery and Cloud Storage client libraries implement the redirect.
    server/bq/proxy.py repairs emulator errors/CSV headers and resolves
    quoted dataset INFORMATION_SCHEMA.TABLES identity/type columns and the
    core INFORMATION_SCHEMA.COLUMNS fields from its live REST catalog;
    other metadata columns remain unsupported.
    Cloud Logging has no such variable,
    so it gets redirect/snowflake's treatment instead. The service-account
    key is real RSA with a token_uri on server/bq/token_stub.py, because
    BIGQUERY_EMULATOR_HOST rewrites the endpoint without waiving the
    credential.
    """
    from services import logging_api

    cli = vendored(
        REPO_ROOT / "vendor" / "google-cloud-mcp" / ".venv" / "bin" /
        "google-cloud-mcp", "uv run python server/mcp/setup_google_cloud.py")
    allowed = gcp_allowed(at.task_dir)
    key = Path(
        os.environ.get(
            "GCP_SERVICE_ACCOUNT",
            toolathlon_path() / "configs" / "gcp-service_account.keys.json"))
    if not key.is_file():
        raise FileNotFoundError(
            f"no service-account key at {key}; "
            f"start the fake with "
            f"`uv run python server/fakes/gcp.py {at.task_dir.name}`")
    project = json.loads(key.read_text())["project_id"]
    return {
        "command":
        str(cli),
        "args": [
            "--project-id",
            project,
            "--service-account-path",
            str(key),
            "--allowed-buckets",
            allowed["buckets"],
            "--allowed-datasets",
            allowed["bigquery_datasets"],
            "--allowed-log-buckets",
            allowed["log_buckets"],
            "--allowed-instances",
            allowed["instances"],
        ],
        "env": {
            **os.environ,
            "BIGQUERY_EMULATOR_HOST":
            os.environ.get("BIGQUERY_EMULATOR_HOST", "http://127.0.0.1:9050"),
            # google-cloud-storage reads this in `Client.__init__` and
            # rewrites the endpoint whatever credential it was handed,
            # which is what points the server's `storage.Client
            # .from_service_account_json` at bin/start.sh up's fake.
            # Defaulted for the same reason as the line above: an unset
            # variable is not "no storage", it is the live service.
            "STORAGE_EMULATOR_HOST":
            os.environ.get("STORAGE_EMULATOR_HOST", "http://127.0.0.1:9070"),
            # Cloud Logging is the one service with neither an emulator
            # nor an endpoint override, so the shim still replaces the
            # transport at interpreter start-up -- but the replacement is
            # a thin HTTP client on the fixture API, one per-task endpoint
            # for either arm's launch of this server.
            "CLOUD_LOGGING_API":
            logging_api(at.task_dir.name),
            "PYTHONPATH":
            str(REPO_ROOT / "redirect" / "cloud_logging"),
        },
        "cwd":
        at.workdir,
    }


def google_sheet(at: Launch) -> dict:
    """The sheets server, in either the upstream or the GYM flavour.

    "upstream" is the unmodified server aimed at the mock GWS through
    redirect/gws_sheets, which is what Toolathlon runs and what
    the mirage arm shares a fixture with. "gym" is GYM's fork, which replaced
    the Google client with PostgreSQL (pg_services.py) and so needs
    task/toolathlon/<task>/gym/seed_pg.py instead.

    Research Sheets tasks restore the original public workbook export in a
    separate local Mirage fixture for each arm. Their original preprocessing
    copies it into the task folder; both surfaces use that folder. Generated
    IDs and placeholder OAuth live in a private task tree for the original
    grader. Workbook titles come from the public Sheet, not sanitized export
    filenames. The fixture mints Google-shaped file IDs so original ID/name
    detection works. No server tools, descriptions or schemas are replaced.
    The task-local `sheets` CLI calls these same original handlers through
    server/clients/original_tools.py; it exposes no general Google API tree.

    Divergence: upstream runs this server inside its task container, beside
    the model's Python and terminal, with CREDENTIALS_PATH and TOKEN_PATH at
    configs/google_credentials.json, and its run script copies configs/ into
    that container's /workspace/configs, so model code can find a live OAuth
    token there. Here the server runs on this host with a fake token, and
    the container the model's code runs in holds no Google credentials.
    """
    if at.sheets == "gym":
        # GYM's compose sets these for its containerised run; on the host
        # they are ours, and the fork defaults to a database that does not
        # exist.
        return {
            "command":
            "uv",
            "args": [
                "--directory",
                str(at.vendored / "mcp-google-sheets"), "run",
                "mcp-google-sheets"
            ],
            "env": {
                **os.environ,
                "PGHOST":
                os.environ.get("PGHOST", "localhost"),
                "PGPORT":
                os.environ.get("PGPORT", "5432"),
                "PGUSER":
                os.environ.get("PGUSER", "eigent"),
                "PGPASSWORD":
                os.environ.get("PGPASSWORD", "camel"),
                "PGDATABASE":
                os.environ.get("PGDATABASE", "toolathlon_gym"),
                "DRIVE_FOLDER_ID":
                os.environ.get("GYM_FOLDER_ID", "nhl-b2b-folder"),
                "CREDENTIALS_PATH":
                "",
                "TOKEN_PATH":
                "",
            },
        }
    shim = str(REPO_ROOT / "redirect" / "gws_sheets")
    # Freeze the full existing uvx resolution for every Sheets task.
    # Only transport is redirected; server code and tool schemas are
    # upstream's.
    launch = {
        "command":
        "uv",
        "args": [
            "run", "--locked", "--directory",
            str(REPO_ROOT / "vendor/google-sheets-mcp"), "mcp-google-sheets"
        ],
        "env": {
            **os.environ,
            "PYTHONPATH": shim,
            "GWS_MOCK_URL": os.environ.get("GWS_URL",
                                           "http://127.0.0.1:19999"),
            "TOKEN_PATH": f"{shim}/fake_token.json",
            "CREDENTIALS_PATH": "/nonexistent.json",
            "SERVICE_ACCOUNT_PATH": "/nonexistent.json",
            "DRIVE_FOLDER_ID": os.environ.get("DRIVE_FOLDER_ID", "f0001"),
        },
    }

    return launch


def google_calendar(at: Launch) -> dict:
    """The calendar server, aimed at the mock GWS by an import hook.

    Upstream runs `npx -y @gongrzhe/server-calendar-autoauth-mcp` against a
    real Google account. server/mcp/setup_calendar.py vendors that server
    pinned and unmodified; redirect/gws_calendar/calendar_hook.mjs gives
    every googleapis call a rootUrl on the mock GWS, which is the same
    fixture the mirage arm's `calendar` CLI reads. The two CALENDAR_* paths
    are the fake OAuth that gets it past its own startup checks. The task-local
    `calendar` CLI calls these same original handlers through
    server/clients/original_tools.mjs; it exposes only the five listed tools.
    """
    cli = vendored(
        REPO_ROOT / "vendor" / "calendar-mcp" / "node_modules" / "@gongrzhe" /
        "server-calendar-autoauth-mcp" / "build" / "index.js",
        "uv run python server/mcp/setup_calendar.py")
    return {
        "command":
        "node",
        "args": [
            "--import",
            (REPO_ROOT / "redirect" / "gws_calendar" /
             "calendar_hook.mjs").as_uri(),
            str(cli)
        ],
        "env": {
            **os.environ,
            **gws_calendar_env(),
        },
        "cwd":
        at.workdir,
    }


def github(at: Launch) -> dict:
    """Upstream's own server, aimed at mirage's fake instead of github.com.

    Two things make that possible and both are documented where they are
    done: server/mcp/setup_github.py builds upstream's pinned commit for this
    machine, because the binary Toolathlon ships is a Linux ELF and says so
    itself, and patches `newGHESHost` to keep the port, which upstream drops
    with a comment saying development environments are out. `--gh-host` is
    the only place a base URL can be set, and any host that is not
    github.com is read as Enterprise, so the fake serves the API under
    /api/v3 as well as at the root.
    """
    cli = vendored(
        REPO_ROOT / "vendor" / "github-mcp-server" / "github-mcp-server",
        "uv run python server/mcp/setup_github.py")
    return {
        "command":
        str(cli),
        "args": [
            "stdio", "--gh-host",
            os.environ.get("GITHUB_URL", "http://127.0.0.1:19801")
        ],
        "env": {
            **os.environ,
            # The fake authenticates on the header being present, not on
            # its value, and answers as one fixed login. Upstream fills
            # these from a real account's token block.
            "GITHUB_PERSONAL_ACCESS_TOKEN":
            "fake-token",
            **github_access(at.task_dir),
        },
        "cwd":
        at.workdir,
    }


def memory(at: Launch) -> dict:
    """The reference memory server, pinned.

    Upstream runs `npx -y @modelcontextprotocol/server-memory`, unpinned;
    server/mcp/setup_memory.py pins it, because the version decides the tool
    surface and the tool surface is half of what the MCP arm is measured on.
    Nothing is redirected: the server is a local store over
    MEMORY_FILE_PATH, which upstream already points at the task's own
    memory.json inside the agent workspace, so the mirage arm reads that
    same file off the workspace mount. The memory CLI serves the same pinned
    entry over the same file.
    """
    cli = vendored(
        REPO_ROOT / "vendor" / "memory-mcp" / "node_modules" /
        "@modelcontextprotocol" / "server-memory" / "dist" / "index.js",
        "uv run python server/mcp/setup_memory.py")
    return {
        "command": "node",
        "args": [str(cli)],
        "env": {
            **os.environ, "MEMORY_FILE_PATH":
            f"{at.workdir}/memory/memory.json"
        },
        "cwd": at.workdir,
    }


def paper_server(kind):

    def build(at: Launch) -> dict:
        """Original pinned paper handlers and arguments.

        Launcher divergence: the locked Python interpreter replaces uv/uvx;
        scripts, wrapper flags and entry points remain upstream's. LaTeX
        runs in the agent workspace with an isolated private cache.
        Transport divergence: every request reaches arXiv and Scholar live
        on both arms through one recording proxy, nothing is kept, and each
        run records every request with its time and response hash. File
        state and the original LaTeX cache are isolated per arm. The VFS
        CLI calls the same handlers directly in the same dependency
        environment.
        """
        from server.seed.papers import parameters
        upstream_config(TIMEOUT_CONFIG.get(kind, kind))
        return parameters(kind, at.workdir)

    return build


def google_forms(at: Launch) -> dict:
    """Original five Forms tools and full npm lock from upstream Docker.

    Transport divergence: Google API requests use the isolated Mirage fixture
    and placeholder OAuth credentials. The original handlers and tool schemas
    are unchanged. The lock replaces upstream's moving npm audit fix step.
    VFS calls the same handlers through a separate CLI worker.
    """
    upstream_config("google_forms")
    from server.clients import gws
    from server.mcp.setup_papers_forms import source_root
    source = source_root("forms-mcp") / "build/index.js"
    return {
        "command": "node",
        "args": [str(source)],
        "env": {
            **os.environ, "GOOGLE_CLIENT_ID":
            "fixture",
            "GOOGLE_CLIENT_SECRET":
            "fixture",
            "GOOGLE_REFRESH_TOKEN":
            gws.TOKEN,
            "GWS_MOCK_URL":
            os.environ["GWS_URL"],
            "NODE_OPTIONS":
            "--import=" + str(REPO_ROOT / "redirect/forms/google_hook.mjs")
        },
    }


def browser(at: Launch) -> dict:
    """Original locked browser server, arguments, schemas and responses.

    Transport divergence: Kubernetes tasks run over SSH inside E2B; other
    browser tasks run in local containers with only the run workspace mounted.
    Local root launch uses upstream's --no-sandbox handling; the container
    provides the filesystem boundary. Their
    Chromium, user agent, isolation, output directory, image policy and
    snapshot span are the original config's. The VFS CLI invokes the same
    package's backend handlers through a separate per-arm worker. Local
    /work paths map to the run directory. The unchanged shopping grader
    uses this pinned local launcher instead of resolving bare npx.
    """
    from server.mcp.setup_browser import PACKAGE, arguments
    from server.shared_workspace import active
    if remote := active():
        entry = ('/opt/browser/vendor/browser-mcp/node_modules/' + PACKAGE +
                 '/cli.js')
        return remote.launch(['node', entry, *arguments('/work')])
    from server.seed.browser import local_params
    return local_params(at.workdir)


def notion(at: Launch) -> dict:
    """Upstream's own server, aimed at mirage's fake instead of notion.com.

    No shim is needed: the server reads its OpenAPI spec's base URL from
    BASE_URL, so both arms reach the one fixture bin/start.sh up seeds.
    The bearer token is the workspace, matching the mirage arm's notion
    mount api_key.

    --page-id is upstream's, and it is not a scope: the server only
    advertises it in its instructions. Toolathlon fills it from the page its
    preprocess duplicated; here it is the fixture's own page id.

    Run the vendored copy, not `npx -y`: server/mcp/setup_notion.py pins 1.9.0
    and overlays Toolathlon's patched OpenAPI spec, which is what fixes the
    arm's tool surface at upstream's 19 rather than whatever the newest
    release advertises. The package resolves its spec from a path relative
    to its own directory, so the overlay needs a real install to sit in.
    Absolute, because the server runs with cwd set to the agent workspace.
    One install serves every notion task -- the workspace it talks to is
    chosen by BASE_URL and the bearer token below, not by the install.
    """
    cli = vendored(
        REPO_ROOT / "vendor" / "notion-mcp" / "node_modules" / "@notionhq" /
        "notion-mcp-server" / "bin" / "cli.mjs",
        "uv run python server/mcp/setup_notion.py")
    return {
        "command": "node",
        "args": [str(cli), "--page-id",
                 notion_page_id(at.task_dir)],
        "env": {
            **os.environ,
            "BASE_URL":
            os.environ.get("NOTION_URL", "http://127.0.0.1:5091"),
            "OPENAPI_MCP_HEADERS":
            json.dumps({
                "Authorization": f"Bearer {notion_workspace(at.task_dir)}",
                "Notion-Version": "2022-06-28",
            }),
        },
        "cwd": at.workdir,
    }


def howtocook(at: Launch) -> dict:
    """The recipe server, pinned to the corpus the ground truth came from.

    Upstream runs `npx -y howtocook-mcp`, which resolves whatever npm
    publishes on the day. Both tasks that use this server grade against a
    static ground truth derived from its recipe corpus, so a corpus that
    moves makes them unpassable rather than merely irreproducible.
    server/mcp/setup_howtocook.py pins 0.2.2, whose corpus is the one the
    ground truth was built from and which it reads from disk with no network
    call at all.
    """
    # The cooking grader refreshes its fallback config to this same pinned
    # server before every evaluation; neither arm resolves npm at run time.
    from services import howtocook_home

    cli = vendored(howtocook_home() / "build" / "index.js",
                   "uv run python server/mcp/setup_howtocook.py")
    return {
        "command": "node",
        "args": [str(cli)],
        "cwd": at.workdir,
    }


def fetch(at: Launch) -> dict:
    """The fetch server, reading the task's capture instead of the internet.

    Upstream runs `npx -y @tokenizin/mcp-npx-fetch`, unpinned and against
    the live internet. server/mcp/setup_fetch.py pins it, and `--import
    redirect/fetch/fetch_hook.mjs` swaps `globalThis.fetch` for the task's
    capture -- upstream's four tools, their schemas and their transforms all
    unchanged, only the bytes redirected. The mirage arm's `fetch` CLI runs
    these same hooked handlers over the same capture.
    """
    cli = vendored(
        REPO_ROOT / "vendor" / "fetch-mcp" / "node_modules" / "@tokenizin" /
        "mcp-npx-fetch" / "dist" / "index.js",
        "uv run python server/mcp/setup_fetch.py")
    # Research tasks retain all original handlers and optional request headers.
    # Public pages are read live on both arms each time they are asked for
    # and nothing is kept; the VFS CLI calls those same handlers directly,
    # without an MCP client.
    # Every task declaring web_search keeps the original local tool/schema;
    # its handler redacts credentials from upstream errors and logs.
    from server.seed.research import TASKS
    if at.task_dir.name in TASKS:
        return {
            'command':
            'node',
            'args': [
                '--import',
                str(REPO_ROOT / 'redirect/research/fetch_hook.mjs'),
                str(cli)
            ],
            'env': {
                'WEB_API_URL': os.environ['WEB_API_URL']
            },
            'cwd':
            at.workdir,
        }
    return {
        "command":
        "node",
        "args": [
            "--import",
            str(REPO_ROOT / "redirect" / "fetch" / "fetch_hook.mjs"),
            str(cli),
        ],
        "env": {
            "WEB_FIXTURE": str(web_fixture(at.task_dir))
        },
        "cwd":
        at.workdir,
    }


def pdf_tools(at: Launch) -> dict:
    """Toolathlon's own local wrapper around the pdf-tools package.

    Divergence: a locked project replaces upstream's dynamic uvx resolution.
    It fixes pdf-tools-mcp 0.1.4, PyPDF2 3.0.1 and all transitive packages,
    including the pre-2 MCP SDK. The upstream RLock wrapper and args remain.

    The PDF CLI reuses this launch and its search sessions. Its transport
    maps file arguments and status paths between /workspace and the backing
    directory; PDF text, metadata and search matches remain unchanged.

    It keeps its public network on both arms, as upstream's has: every tool
    that takes a PDF tells the model it takes a URL too, and downloads it
    (`download_pdf_from_url`). Without the network, a URL the model passed
    failed to resolve where upstream's would have downloaded it.
    """
    wrapper = (toolathlon_path() / "utils" / "local_servers" /
               "pdf_tools_local_wrapper.py")
    return {
        "command":
        "uv",
        "args": [
            "run",
            "--locked",
            "--project",
            str(REPO_ROOT / "vendor" / "pdf-tools-mcp"),
            "python",
            str(wrapper),
            "--workspace_path",
            at.workdir,
            "--tempfile_dir",
            f"{at.workdir}/.pdf_tools_tempfiles",
        ],
        "cwd":
        at.workdir,
    }


def huggingface(at: Launch) -> dict:
    """Upstream's bridge into the live Hub or a captured task fixture.

    vlm-history-completer keeps the original public HTTPS endpoint. A bearer
    is supplied only when configured; anonymous public access is supported.
    Its tool list remains live. The fixture behavior below is for other tasks.

    This is the one server upstream points at a URL rather than a package:
    `npx mcp-remote https://huggingface.co/mcp` with a bearer, so the tools
    live at the far end and there is no library here to re-point. The
    endpoint moves and the bridge stays, which is the same substitution the
    other servers make -- mcp-remote relays a tool document rather than
    owning one.

    What the endpoint answers with is not authored either: mirage captures
    the live server's own `tools/list` into fixtures/hf-mcp/tools.json and
    replays it verbatim, because a hand-written schema here would put a
    mirage-shaped tool surface in front of the thing being measured.

    Two divergences from upstream's line, both forced:

    * the bridge is vendored at a pinned version, where `npx mcp-remote`
      resolves whatever npm published that morning;
    * `--allow-http`, because the endpoint is 127.0.0.1 and not https. The
      bridge refuses plain HTTP otherwise, and it is refusing on the ground
      that a token would cross the network in clear -- which is a real
      concern about a real Hub token and not about this one.

    The bearer is the tenant, the way notion's is the workspace: the fake
    reads the token as the tenant name, so the arm sees the task's own
    fixture and not another task's.
    """
    bridge = vendored(
        REPO_ROOT / "vendor" / "mcp-remote" / "node_modules" / "mcp-remote" /
        "dist" / "proxy.js", "uv run python server/mcp/setup_huggingface.py")
    if at.task_dir.name == 'vlm-history-completer':
        args = [str(bridge), 'https://huggingface.co/mcp']
        if os.environ.get('HF_TOKEN'):
            args += [
                '--header', 'Authorization: Bearer ' + os.environ['HF_TOKEN']
            ]
        return {
            'command': 'node',
            'args': args,
            'cwd': at.workdir,
            'env': {
                **os.environ, 'MCP_REMOTE_CONFIG_DIR':
                str(Path(at.workdir) / '.runtime/mcp-auth')
            }
        }
    endpoint = os.environ.get("HF_MCP_URL", "http://127.0.0.1:5200/mcp")
    return {
        "command":
        "node",
        "args": [
            str(bridge),
            endpoint,
            "--allow-http",
            "--header",
            f"Authorization: Bearer {at.task_dir.name}",
        ],
        "cwd":
        at.workdir,
    }


def travel_video_server(kind):

    def build(at):
        """Original handlers and arguments; installed locks replace npx/uvx.

        Maps uses the original npm lock. YouTube and transcript use the
        Dockerfile commits; YouTube has no upstream npm lock, so its complete
        resolved dependency tree is frozen here. Railway retains 0.3.9 and
        its original Node/axios HTTP transport behind the public-services
        transport, live on both arms;
        the edge rejects Python requests on some routes. Bootstrap cookies
        stay fresh. The CLI imports handlers without constructing an MCP
        client. Only transport URLs are redirected; schemas are unchanged.
        """
        from server.seed.travel_video import parameters
        return parameters(kind, at.workdir)

    return build


# Every server this repo can launch, by the name Toolathlon spells it.
# Terminal comes from Toolathlon-GYM's vendored copy. That is not a shortcut,
# it is a correction: upstream terminal.yaml names
# lockon-n's cli-mcp-server fork but runs `uvx cli-mcp-server`, which
# resolves the unrelated PyPI package. Only the fork reads MAX_OUTPUT_LENGTH
# and friends, so under `uvx` those caps are silently ignored. Filesystem and
# Excel instead run the exact dependency trees in Toolathlon's own locks.
SERVERS = {
    **{
        kind: travel_video_server(kind)
        for kind in (
            "google_map",
            "youtube",
            "youtube-transcript",
            "rail_12306",
        )
    },
    "arxiv-latex": paper_server("arxiv-latex"),
    "arxiv_local": paper_server("arxiv_local"),
    "scholarly": paper_server("scholarly"),
    "google_forms": google_forms,
    "canvas": canvas,
    "woocommerce": woocommerce,
    "k8s": kubernetes,
    "filesystem": filesystem,
    "terminal": terminal,
    "git": git,
    "emails": emails,
    "excel": excel,
    "yahoo-finance": yahoo_finance,
    "wandb": wandb,
    "word": office("word"),
    "pptx": office("pptx"),
    "snowflake": snowflake,
    "google-cloud": google_cloud,
    "google_sheet": google_sheet,
    "google_calendar": google_calendar,
    "github": github,
    "memory": memory,
    "playwright_with_chunk": browser,
    "notion": notion,
    "howtocook": howtocook,
    "fetch": fetch,
    "pdf-tools": pdf_tools,
    "huggingface": huggingface,
}


def server_params(name: str,
                  task_dir: Path,
                  workdir: str,
                  sheets: str = "upstream") -> dict:
    """Params for one MCP server, matching Toolathlon's configs/mcp_servers.

    Args:
        name (str): server name as Toolathlon spells it.
        task_dir (Path): task directory.
        workdir (str): the agent workspace.
        sheets (str): "upstream" or "gym", for google_sheet only.

    Returns:
        dict: what `MCPServerStdio` is constructed from.

    Raises:
        NotImplementedError: no builder for that name.
    """
    # The seam's own registry first. The dict below is Toolathlon's surface,
    # and a second dataset naming a server `filesystem` can mean a different
    # package at a different version.
    # Running the wrong one would not be a divergence, it would be a fork, and
    # it would be invisible: the arm would come up, list tools, and measure
    # somebody else's schemas.
    registry = getattr(dataset, "SERVERS", SERVERS)
    build = registry.get(name)
    if build is None:
        raise NotImplementedError(
            f"no builder for MCP server {name!r}; add one to SERVERS")
    return build(Launch(task_dir=task_dir, workdir=workdir, sheets=sheets))


# Upstream's config file name, where it is not the server's own name.
TIMEOUT_CONFIG = {
    "youtube-transcript": "youtube_transcript",
    "rail_12306": "12306",
    "fetch": "npx-fetch",
    "arxiv-latex": "arxiv-latex-mcp",
    "scholarly": "scholarly_search"
}


def upstream_config(name: str) -> str | None:
    """One of upstream's MCP configs, as the pinned commit has it.

    Read out of git rather than off disk, because
    `setup/toolathlon/setup_toolathlon.py` rewrites four of these in place
    so Toolathlon's own runner can be aimed
    at the mocks. Those rewrites are for that runner, not for this repo's
    MCP arm -- which builds its own params in this module and only ever
    consults upstream's yaml for the one thing it does not restate, the
    session timeout. Reading the working tree let one of those rewrites
    leak into a measured number: the calendar rewrite raises the timeout
    from upstream's 10 seconds to 60, and `set-conf-cr-ddl` and
    `student-interview` were being given six times upstream's budget to
    answer a calendar call.

    Args:
        name (str): upstream's file name for the server, without `.yaml`.

    Returns:
        str | None: the file's committed text, or None when there is no
            such config, no checkout, or no git to ask.
    """
    root = toolathlon_path()
    relative = f"configs/mcp_servers/{name}.yaml"
    shown = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{relative}"],
        capture_output=True,
        text=True)
    if shown.returncode == 0:
        return shown.stdout
    exists = subprocess.run(
        ["git", "-C",
         str(root), "cat-file", "-e", f"HEAD:{relative}"],
        capture_output=True)
    if exists.returncode:
        # A genuinely absent optional config differs from a broken checkout.
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            check=True)
        return None
    raise RuntimeError(f"Could not read pinned upstream config: {relative}")


def timeout_for(name: str) -> int | None:
    """How long one server is given to answer a call, per upstream's yaml.

    Read rather than restated, for the reason `needed_mcp_servers` is read:
    a hand-maintained table drifts, and this one had. It listed five
    servers and defaulted the rest to 60, which was wrong in both
    directions against upstream's own `client_session_timeout_seconds` --
    `snowflake` (120), `notion` (100), `fetch` (100) and `howtocook` (1000)
    were being cut to 60, so the MCP arm timed out on calls upstream allows,
    while `git` (10), `word` (10), `pptx` (10), `google-cloud` (30) and
    `github` (50) were being given more than upstream allows, so it
    completed calls upstream would have aborted. Both directions move a
    measured result, and the second flatters the arm this repo is measuring
    against.

    Read from the pinned commit rather than the working tree, for the
    reason `upstream_config` gives.

    None where upstream declares nothing, which is `utils/mcp/
    tool_servers.py:91` exactly: `if timeout := config.get(...)` omits the
    kwarg rather than substituting a number, so the SDK's own default
    stands. Substituting one here was the last restated value in this
    function -- `time.yaml` declares no timeout, and a 60 in its place is
    twelve times the 5 seconds upstream ends up with. No task declares
    `time`, so nothing measured moved, but the whole point of reading
    upstream's file is not to have an opinion about it.

    Args:
        name (str): the server name as Toolathlon spells it.

    Returns:
        int | None: the timeout in seconds, or None to pass no timeout.
    """
    config = upstream_config(TIMEOUT_CONFIG.get(name, name))
    if config is None:
        return None
    found = re.search(r"^client_session_timeout_seconds:\s*(\d+)", config,
                      re.M)
    # Truthiness, not presence, because upstream's walrus treats a declared
    # zero as absent too.
    return int(found.group(1)) or None if found else None


def model_tool_name(name: str) -> str:
    """The name upstream shows the model, from the name a server uses.

    `utils/openai_agents_monkey_patch/tool_name_aliases.py`: hyphens become
    underscores, and an MCP tool is namespaced by its server first, so
    `google_sheet`'s `get_sheet_data` reaches the model as
    `google_sheet_get_sheet_data`. Backend names are left alone on both
    sides of that rename -- it is a display concern that happens to cost
    tokens, since the prefix rides in every definition, every tool call and
    every result.

    Args:
        name (str): the backend name, or `<server>-<tool>` for an MCP tool.

    Returns:
        str: the model-facing name.
    """
    return name.replace("-", "_")


def shown_tool_name(server: str, tool: str) -> str:
    """The model-facing name for one tool on one server.

    Two arguments rather than one joined string because the join is not
    reversible: `mcp-code-executor` and `execute_code` have no single spelling
    a `-` can be split back out of.

    Toolathlon's convention is the default and a dataset that names its tools
    differently says so on its seam. Atlas does, and the rule is read off
    upstream rather than reasoned about: its sandbox composes every server
    into one `fastmcp.Client(config)` (`agent_environment/mcp_client.py:150`),
    which prefixes each tool with its config key; upstream splits that back
    apart with `tool.name.split("_", 1)[0]` (`main.py:221`); and its published
    rows spell the result `mcp-code-executor_execute_code`, hyphens intact.

    Args:
        server (str): the server name.
        tool (str): the tool's own name.

    Returns:
        str: the model-facing name.
    """
    seam = getattr(dataset, "shown_tool_name", None)
    if seam is not None:
        return seam(server, tool)
    return model_tool_name(f"{server}-{tool}")


def aliasing_server(cls):
    """Wrap an MCP server class in upstream's model-facing tool names.

    Upstream renames at the point it converts an MCP tool to a FunctionTool
    (`custom_mcp_util.py:145`), keeping the original tool object in the
    callback so dispatch never needs the name back. That patch targets a
    call path openai-agents 0.18 no longer has, so the rename happens here
    instead -- on the way out of `list_tools`, and undone on the way into
    `call_tool`, which is the same rename with the same two names.

    Args:
        cls: an MCP server class exposing `list_tools` and `call_tool`.

    Returns:
        type: subclass that advertises the model-facing names.
    """

    class Aliasing(cls):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._backend_names: dict = {}

        async def list_tools(self, run_context=None, agent=None):
            tools = await super().list_tools(run_context, agent)
            aliased = []
            for tool in tools:
                shown = shown_tool_name(self.name, tool.name)
                self._backend_names[shown] = tool.name
                aliased.append(tool.model_copy(update={"name": shown}))
            return aliased

        async def call_tool(self, tool_name, arguments, meta=None):
            # `.get` rather than `[]`: a caller that never listed -- the
            # parity tests call one tool by its backend name -- must still
            # reach the server rather than die on a missing alias.
            return await super().call_tool(
                self._backend_names.get(tool_name, tool_name), arguments, meta)

    return Aliasing


def truncating_server(cls):
    """Adapt Toolathlon's serialized MCP output to the current SDK.

    Upstream custom_mcp_util.py serializes the complete content array and
    caps that string. custom_run_impl.py then caps the function result,
    including the first notice. Preserve both passes and their saved bytes.
    The current SDK extracts text from content blocks, so one text block
    carries the already serialized upstream result to the model.

    Other datasets retain their existing text-block adapter; this change
    does not impose Toolathlon's serialization on their protocols.

    Args:
        cls: an MCP server class exposing `call_tool`.

    Returns:
        type: subclass that caps and offloads oversized tool results.
    """
    import shortuuid

    class Truncating(cls):

        async def call_tool(self, tool_name, arguments, meta=None):
            result = await super().call_tool(tool_name, arguments, meta)
            if dataset.NAME == "toolathlon":
                from mcp.types import TextContent

                # Copied from upstream MCPUtil, including its different
                # JSON formatting for one item versus multiple items.
                if len(result.content) == 1:
                    text = result.content[0].model_dump_json()
                elif len(result.content) > 1:
                    text = json.dumps(
                        [item.model_dump() for item in result.content])
                else:
                    text = "[]"
                workdir = os.environ.get("AGENT_WORKSPACE", ".")
                for _ in range(2):
                    if len(text) > MAX_TOOL_OUTPUT:
                        text = services.overlong_note(text, workdir)
                return result.model_copy(
                    update={
                        "content": [TextContent(type="text", text=text)],
                        "structuredContent": None,
                    })
            # Budget the whole result, not each block: servers chunk large
            # reads across many content blocks, so a per-block cap would let
            # N x MAX_TOOL_OUTPUT through and would not match the shell arm.
            blocks = [
                b for b in (getattr(result, "content", None) or [])
                if getattr(b, "text", None) is not None
            ]
            total = sum(len(b.text) for b in blocks)
            if total <= MAX_TOOL_OUTPUT:
                return result

            save_dir = Path(os.environ.get("AGENT_WORKSPACE", ".")).resolve()
            save_dir = save_dir / ".overlong_tool_outputs"
            save_dir.mkdir(parents=True, exist_ok=True)
            short_uuid = shortuuid.uuid()
            path = save_dir / f"{short_uuid}.json"
            path.write_text("".join(b.text for b in blocks), encoding="utf-8")
            from server.shared_workspace import active
            if remote := active():
                remote.save(f'.overlong_tool_outputs/{short_uuid}.json',
                            path.read_bytes())
                path = Path('/work/.overlong_tool_outputs') / path.name

            budget = MAX_TOOL_OUTPUT
            for block in blocks:
                if len(block.text) <= budget:
                    budget -= len(block.text)
                    continue
                block.text = block.text[:budget]
                budget = 0
            blocks[-1].text += (
                f" ...\n\n(The output of the tool call (shortuuid identifier: "
                f"{short_uuid}) is too long! Only the first "
                f"{MAX_TOOL_OUTPUT} characters are shown here. The original "
                f"output length is {total} characters. The full output has "
                f"been saved to the file {path}. Please check this file "
                f"carefully, as it may be very long!)")
            return result

    Truncating.__name__ = f"Truncating{cls.__name__}"
    return Truncating


def build_mcp_servers(task_dir: Path,
                      workdir: str,
                      sheets: str = "upstream") -> list:
    """Build the MCP servers the original Toolathlon arm uses.

    Driven by the task's own `needed_mcp_servers`, so adding a task costs
    nothing here unless it is the first to need a given server.

    Args:
        task_dir (Path): task directory.
        workdir (str): directory the servers may touch.
        sheets (str): "upstream" or "gym".

    Returns:
        list: unstarted MCP server instances.
    """
    # A dataset whose harness composes its servers its own way builds them
    # itself -- Atlas, whose app neither renames nor caps -- and everything
    # below is Toolathlon's composition.
    own = getattr(dataset, "build_mcp_servers", None)
    if own is not None:
        return own(task_dir, workdir)

    from agents.mcp import MCPServerStdio as _Stdio
    from agents.mcp import MCPServerStreamableHttp as _Http

    # Aliasing outermost: it renames on the way out of `list_tools`
    # and back on the way into `call_tool`, so every layer below it
    # -- and the server itself -- only ever sees a backend name.
    MCPServerStdio = aliasing_server(truncating_server(_Stdio))
    MCPServerHttp = aliasing_server(truncating_server(_Http))
    servers = []
    for name in needed_mcp_servers(task_dir):
        # nvidia-stock-analysis declares a nonexistent web_search server.
        # Original MCPServerManager.connect_servers warns and skips it;
        # it does not substitute the Serper local tool or another server.
        if (dataset.NAME == 'toolathlon'
                and task_dir.name == 'nvidia-stock-analysis'
                and name == 'web_search' and upstream_config(name) is None):
            print(f"Warning: Server '{name}' not found")
            continue
        params = server_params(name, task_dir, workdir, sheets)
        # Divergence: native processes are confined to the run workspace,
        # their installed dependencies and explicit fixture files. Operator
        # model/E2B credentials are excluded. This wraps the launch only;
        # upstream server code, arguments and tool schemas stay unchanged.
        # The filesystem and terminal servers in upstream's container have
        # its boundary instead, as upstream's do.
        from server.shared_workspace import active
        if ("command" in params and dataset.NAME == "toolathlon"
                and active() is None and name != 'playwright_with_chunk'
                and params["command"] != "docker"):
            sys.path.insert(0, str(REPO_ROOT))
            from server.execution import launch, prepare
            prepare(params)
            readable = ([
                REPO_ROOT / 'server/clients', REPO_ROOT / 'server/__init__.py'
            ] if name in {'google-cloud', 'snowflake'} else [])
            if name == 'google_calendar':
                # --import names a file URL, not an absolute argv path.
                readable += [
                    REPO_ROOT / 'redirect/gws_calendar/calendar_hook.mjs'
                ]
            if name == 'git':
                # uv runs it from its own source tree, which it must read
                # to resolve its working directory at all.
                readable += [Path(params['cwd'])]
            if name == 'youtube-transcript':
                # The pinned package is installed editable from this source.
                readable += [REPO_ROOT / 'vendor/youtube-transcript-mcp']
            if name == 'google_forms':
                readable += [
                    REPO_ROOT / 'redirect/forms',
                    REPO_ROOT / 'vendor/forms-mcp/src'
                ]
            writable = []
            if name in {'arxiv-latex', 'arxiv_local', 'scholarly'}:
                from server.seed.papers import VENDORS
                readable += [REPO_ROOT / 'vendor' / VENDORS[name]]
                writable = [os.environ['PAPER_CACHE_DIR']]
            params = launch(
                params,
                workdir,
                readable,
                writable,
                public_network=(
                    name in ('youtube', 'youtube-transcript', 'pdf-tools')
                    or (name == 'huggingface'
                        and task_dir.name == 'vlm-history-completer')))
        kwargs = {
            "name": name,
            "params": params,
            "cache_tools_list": True,
        }
        # Conditional, not a default, mirroring utils/mcp/tool_servers.py:91:
        # a server whose yaml declares no timeout gets whichever one the
        # agents SDK ships, and gets it in both harnesses.
        timeout = timeout_for(name)
        if timeout:
            kwargs["client_session_timeout_seconds"] = timeout
        which = MCPServerHttp if "url" in params else MCPServerStdio
        servers.append(which(**kwargs))
    return servers
