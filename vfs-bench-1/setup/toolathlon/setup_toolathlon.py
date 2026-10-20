#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "agent"))

from server.mcp.mcp_servers import upstream_config  # noqa: E402

TASK = REPO / "task" / "toolathlon" / "nhl-b2b-analysis"
OVERRIDES = TASK / "toolathlon" / "overrides"
SHIM = REPO / "redirect" / "gws_sheets"
GWS_URL = os.environ.get("GWS_URL", "http://127.0.0.1:19999")
GYM = REPO / "submodule" / "toolathlon_gym" / "local_servers"
TASK_REL = "tasks/finalpool/nhl-b2b-analysis"

# uvx resolves the newest mcp, but mcp>=2 moved FastMCP and Server.list_tools,
# which breaks both of these servers on startup.
MCP_PIN = ['    - "--with"', '    - "mcp>=1.2,<2"']

# The four configs this script rewrites in place, and where their pinned
# text is kept. The rewrites have to land in the checkout, which is why the
# pinned text needs somewhere else to live: upstream's own evaluators reach
# these servers through `MCPServerManager`, which resolves
# `configs/mcp_servers` against the Toolathlon root -- taking the default
# (`tasks/finalpool/set-conf-cr-ddl/evaluation/main.py:56`) or spelling the
# literal out (`tasks/finalpool/oil-price/evaluation/main.py:942`) -- and
# `mcp_config.server_config_path`, the one knob upstream has for it, only
# reaches `utils/roles/task_agent.py`, which this repo never runs: it builds
# its own servers in `server/mcp/mcp_servers.py` and runs upstream's
# evaluators. `dvc.yaml` depends on the copies rather than on the files in
# the checkout; see `pin_upstream_configs`.
REWRITTEN = ("google_calendar", "google_sheet", "terminal", "yahoo-finance",
             "howtocook")
PINNED = Path(__file__).resolve().parent / "upstream"


def pin_upstream_configs() -> None:
    """Copy the pinned text of every config this script rewrites.

    The rewrites below write this checkout's own absolute paths and its
    resolved `GWS_URL` into four files `dvc.yaml` names as stage
    dependencies, so the hash DVC records identifies the directory the
    checkout happens to live in rather than upstream's content: `dvc.lock`
    matched in exactly one checkout at a time, `dvc status` reported those
    stages changed in every other one, and the `fixture-lineage` hook
    rejected commits made there for a drift that was not one. The stages
    depend on these copies instead -- the same committed bytes
    `mcp_servers.upstream_config()` already reads, and for the same reason.

    Written before the rewrites and read out of git rather than off disk, so
    running setup twice cannot pin a patched file.

    Raises:
        RuntimeError: when upstream no longer commits one of `REWRITTEN`.
            A warning would leave the old copy in place, still matching
            `dvc.lock` and still feeding the stages below it, so the
            lineage would go on asserting a config the checkout does not
            have -- and the rewrite of that same file further down would
            fail on its own terms anyway.
    """
    PINNED.mkdir(parents=True, exist_ok=True)
    for name in REWRITTEN:
        text = upstream_config(name)
        if text is None:
            raise RuntimeError(
                f"submodule/Toolathlon HEAD commits no "
                f"configs/mcp_servers/{name}.yaml; "
                f"{(PINNED / f'{name}.yaml').relative_to(REPO)} would keep "
                f"a config upstream removed or renamed")
        (PINNED / f"{name}.yaml").write_text(text)
    print(f"  pinned {len(REWRITTEN)} upstream configs under "
          f"{PINNED.relative_to(REPO)}")


def install_file(src: Path, dst: Path) -> None:
    """Replace an upstream file with the task's own copy of it.

    The original is not saved beside it. It does not need to be: the file
    is tracked by the submodule, so `git -C submodule/Toolathlon diff` says
    what changed and `git checkout` undoes it. A `.bak` would be worse than
    nothing here -- running setup twice would overwrite the backup with the
    already-patched copy, and the original would be gone for good.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  installed {dst.relative_to(dst.parents[4])}")


def pin_mcp(yaml_path: Path, package: str) -> None:
    """Add `--with mcp>=1.2,<2` to a server's uvx args, once."""
    text = yaml_path.read_text()
    if "mcp>=1.2,<2" in text:
        return
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == f'- "{package}"':
            lines[i:i] = MCP_PIN
            break
    else:
        print(f"  WARNING: could not pin mcp in {yaml_path.name}")
        return
    yaml_path.write_text("\n".join(lines) + "\n")
    print(f"  pinned mcp<2 in {yaml_path.name}")


def point_sheets_at_mock(yaml_path: Path) -> None:
    """Add the shim env so mcp-google-sheets targets the mock server."""
    import yaml
    config = yaml.safe_load(yaml_path.read_text())
    config['params']['command'] = 'uv'
    config['params']['args'] = [
        'run', '--locked', '--directory',
        str(REPO / 'vendor/google-sheets-mcp'), 'mcp-google-sheets'
    ]
    config['params'].setdefault('env', {}).update(
        PYTHONPATH=str(SHIM),
        GWS_MOCK_URL=GWS_URL,
        SERVICE_ACCOUNT_PATH='/nonexistent.json')
    yaml_path.write_text(yaml.safe_dump(config, sort_keys=False))


def point_yahoo_at_gym(yaml_path: Path) -> None:
    """Rewrite yahoo-finance.yaml to run the gym's server, live.

    Upstream resolves this server as `${local_servers_paths}/...`, which is
    `./local_servers` relative to the Toolathlon checkout -- a directory that
    exists in their deployment and not in this one, so the server simply
    fails to start. Only `oil-price` notices, and it notices in the worst
    possible way: its evaluator wraps the whole Yahoo pull in `except
    Exception: pass`, and with no prices it has nothing to compare against
    and reports success without checking anything.

    The replacement is the same server this repo's MCP arm runs -- the gym's
    copy, reading the original SDK live as upstream's does. Upstream's
    client hands the server only the env its config names, so the recording
    transport's two addresses are written in whenever a run has them; the
    grader rewrites this file on every grade, inside the run's services.

    Args:
        yaml_path (Path): configs/mcp_servers/yahoo-finance.yaml.
    """
    text = yaml_path.read_text()
    start = text.find("params:")
    end = text.find("\nclient_session_timeout_seconds:")
    if start < 0 or end < 0:
        print(f"  WARNING: unrecognised {yaml_path.name}, not rewritten")
        return
    block = "\n".join([
        "params:",
        '  command: "uv"',
        "  args:",
        '    - "run"',
        '    - "--locked"',
        '    - "--directory"',
        f'    - "{REPO / "vendor/yahoo-finance-mcp"}"',
        '    - "python"',
        '    - "-c"',
        '    - "import runpy,sys;'
        'runpy.run_path(sys.argv[1],run_name=\'__main__\')"',
        f'    - "{GYM / "yahoo-finance-mcp/server.py"}"',
        "  env:",
        f'    PYTHONPATH: "{REPO / "redirect/yahoo_capture"}"',
        *(f'    {key}: "{os.environ[key]}"'
          for key in ("PUBLIC_SERVICE_URL", "YAHOO_CLI_URL")
          if os.environ.get(key)),
    ])
    yaml_path.write_text(text[:start] + block + text[end:])
    print(f"  pointed {yaml_path.name} at the gym's server")


def point_howtocook_at_pinned(yaml_path: Path) -> None:
    """Keep the grader's fallback on the same pinned recipe server."""
    import yaml
    from services import howtocook_home

    from server.mcp.mcp_servers import vendored
    home = howtocook_home()
    entry = vendored(home / 'build/index.js',
                     'uv run python server/mcp/setup_howtocook.py')
    if not (home / 'all_recipes.json').is_file():
        raise RuntimeError('The pinned recipe corpus is missing; run setup')
    config = yaml.safe_load(upstream_config('howtocook'))
    config['params'].update(command='node', args=[str(entry)])
    yaml_path.write_text(yaml.safe_dump(config, sort_keys=False))


def point_calendar_at_mock(yaml_path: Path) -> None:
    """Rewrite google_calendar.yaml to run the vendored server on the mock.

    A calendar evaluator reads the calendar back by spawning this server
    itself, so it has to reach the same fixture the agent wrote to. One
    thing changes and nothing else does: the command becomes the pinned copy
    `server/mcp/setup_calendar.py` vendors, loaded through
    `redirect/gws_calendar/calendar_hook.mjs`.

    `client_session_timeout_seconds` is deliberately left at upstream's 10.
    It was raised to 60 here on the theory that a cold `npx` resolve loses
    the race -- but the same rewrite replaces `npx` with a vendored `node`
    path, which has nothing to resolve, so the bump bought nothing and cost
    a measurement: `server/mcp/mcp_servers.timeout_for` read this file off
    disk, so `set-conf-cr-ddl` and `student-interview` were run with six
    times upstream's budget for a calendar call. It reads the pinned commit
    now, but the file it rewrites should still say what upstream says.

    The server's own code, tools and schemas are untouched; only its
    `rootUrl` and its OAuth files are.

    Args:
        yaml_path (Path): configs/mcp_servers/google_calendar.yaml.
    """
    text = yaml_path.read_text()
    start = text.find("params:")
    end = text.find("\nclient_session_timeout_seconds:")
    if start < 0 or end < 0:
        print(f"  WARNING: unrecognised {yaml_path.name}, not rewritten")
        return
    server = (REPO / "vendor" / "calendar-mcp" / "node_modules" / "@gongrzhe" /
              "server-calendar-autoauth-mcp" / "build" / "index.js")
    fake = REPO / "redirect" / "gws_calendar"
    block = "\n".join([
        "params:",
        "  command: node",
        "  args:",
        '    - "--import"',
        f'    - "{(fake / "calendar_hook.mjs").as_uri()}"',
        f'    - "{server}"',
        "  env:",
        f'    GWS_MOCK_URL: "{GWS_URL}"',
        f'    CALENDAR_OAUTH_PATH: "{fake / "gcp-oauth.keys.json"}"',
        f'    CALENDAR_CREDENTIALS_PATH: "{fake / "credentials.json"}"',
        '  cwd: "${agent_workspace}"',
    ])
    # Compared against the block itself rather than asked whether the file
    # has been touched at all. The guard here was `if "GWS_MOCK_URL" in
    # text: return`, which made a *wrong* rewrite permanent: this line named
    # `server/mcp/calendar_hook.mjs` from the commit that created
    # `redirect/` until the one that fixed it, and re-running setup could
    # never repair it. Both calendar tasks graded `eval_exit=1` for the
    # whole of that window -- upstream's evaluator spawns this server
    # itself, times out at 10s against a module that does not exist, and
    # the MCP arm never noticed because `mcp_servers.py` builds its own
    # arguments and had the path right.
    if text[start:end] == block:
        return
    yaml_path.write_text(text[:start] + block + text[end:])
    print(f"  pointed {yaml_path.name} at {GWS_URL}")


def write_configs(root: Path) -> None:
    """Create global_configs.py / token_key_session.py from the templates."""
    cfg = root / "configs"
    # Several evaluators read `configs/google_credentials.json` by that
    # literal path rather than through token_key_session, so pointing
    # google_oauth2_token_path at the shim's copy does not reach them. The
    # token has to satisfy `Credentials.from_authorized_user_file`, look
    # unexpired, and be the mock's own fixture token. Never replaced when a
    # real checkout has a real one here, but a mock copy is refreshed: one
    # written before the mock checked its token carries one it refuses. A
    # file this cannot read as an object is not a mock copy, so it stays.
    target = cfg / "google_credentials.json"
    token = json.loads((SHIM / "fake_token.json").read_text())
    try:
        current = json.loads(target.read_text())
    except FileNotFoundError:
        current = {"client_id": token["client_id"]}
    except (OSError, ValueError):
        current = None
    if (isinstance(current, dict)
            and current.get("client_id") == token["client_id"]
            and current != token):
        shutil.copy2(SHIM / "fake_token.json", target)
        print("  wrote configs/google_credentials.json (mock token)")
    target = cfg / "global_configs.py"
    if not target.exists():
        shutil.copy2(cfg / "global_configs_example.py", target)
        print("  created configs/global_configs.py")

    target = cfg / "token_key_session.py"
    if not target.exists():
        text = (cfg / "token_key_session_example.py").read_text()
        text = text.replace(
            'google_oauth2_credentials_path = '
            '"configs/google_credentials.json"',
            'google_oauth2_credentials_path = "/nonexistent.json"')
        text = text.replace(
            'google_oauth2_token_path = "configs/google_credentials.json"',
            f'google_oauth2_token_path = "{SHIM}/fake_token.json"')
        target.write_text(text)
        print("  created configs/token_key_session.py (auth -> mock)")


def main() -> int:
    default = REPO / "submodule" / "Toolathlon"
    root = Path(os.environ.get("TOOLATHLON_ROOT",
                               default)).expanduser().resolve()
    if not (root / "main.py").exists():
        print(
            f"error: no Toolathlon checkout at {root}\n"
            f"clone https://github.com/hkust-nlp/Toolathlon and set "
            f"TOOLATHLON_ROOT",
            file=sys.stderr)
        return 2
    print(f"applying overrides to {root}")

    write_configs(root)

    # Upstream preprocess copies a live public spreadsheet and upstream
    # evaluation uses the original grader with a gspread transport redirect.
    install_file(OVERRIDES / "preprocess_main.py",
                 root / TASK_REL / "preprocess" / "main.py")
    # Migrate only the grader this setup previously installed. Other local
    # edits are left alone; the grader launcher rejects them.
    grader = root / TASK_REL / "evaluation" / "main.py"
    import hashlib
    if hashlib.sha256(grader.read_bytes()).hexdigest(
    ) == "89ec0dc7eff9f005973fdc1fd3bfab684841c31c5332dcfa9ae04bd14db80226":
        grader.write_bytes(
            subprocess.check_output([
                "git", "-C",
                str(root), "show", f"HEAD:{TASK_REL}/evaluation/main.py"
            ]))

    pin_upstream_configs()

    pin_mcp(root / "configs/mcp_servers/google_sheet.yaml",
            "mcp-google-sheets")
    pin_mcp(root / "configs/mcp_servers/terminal.yaml", "cli-mcp-server")
    point_sheets_at_mock(root / "configs/mcp_servers/google_sheet.yaml")
    point_yahoo_at_gym(root / "configs/mcp_servers/yahoo-finance.yaml")
    point_calendar_at_mock(root / "configs/mcp_servers/google_calendar.yaml")

    print("done. run `uv sync` in the checkout if you have not already.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
