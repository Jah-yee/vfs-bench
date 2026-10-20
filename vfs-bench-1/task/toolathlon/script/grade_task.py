#!/usr/bin/env python
import argparse
import asyncio
import calendar
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT / "agent"))
sys.path.insert(0, str(REPO_ROOT / "task"))

import dataset  # noqa: E402
from services import agent_workspace  # noqa: E402
from services import seeded_workspace  # noqa: E402
from services import yf_dsn  # noqa: E402
from services import ground_truth as generated_truth  # noqa: E402

UPSTREAM = dataset.root().joinpath(*dataset.POOL)


def verify_oil_prices(rows: list) -> None:
    """Require real closes, so the evaluator has prices to score."""
    try:
        if not rows or not all(
                math.isfinite(float(row['Close'])) for row in rows):
            raise ValueError('Non-finite close')
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError('Oil numeric grading has invalid prices') from error


def oil_months(now: datetime) -> list[str]:
    """The twelve complete months the evaluator scores, oldest first.

    Upstream's `_get_expected_months`, on the same UTC clock.
    """
    months = []
    year, month = now.year, now.month
    for _ in range(12):
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
        months.append(f'{year:04d}-{month:02d}')
    return months[::-1]


async def verify_oil_months(session, ticker: str, rows: list,
                            now: datetime) -> None:
    """Price every month the evaluator scores, the way it will.

    A month the monthly series skips is priced by date on its last day, as
    upstream's evaluator does; one that still has no price drops out of
    its comparison without a word, so it fails here instead.
    """
    priced = {
        datetime.fromisoformat(str(row['Date']).replace(
            'Z', '+00:00')).strftime('%Y-%m')
        for row in rows
    }
    missing = []
    for month in oil_months(now):
        if month in priced:
            continue
        year, number = map(int, month.split('-'))
        date = f'{month}-{calendar.monthrange(year, number)[1]:02d}'
        result = await session.call_tool('get_stock_price_by_date', {
            'ticker': ticker,
            'date': date
        })
        try:
            close = float(json.loads(result.content[0].text)['close'])
        except (IndexError, KeyError, TypeError, ValueError):
            close = math.nan
        if result.isError or not math.isfinite(close):
            missing.append(month)
    if missing:
        raise RuntimeError(f'Oil numeric grading cannot price {ticker} for '
                           f'{", ".join(missing)}')


async def verify_oil_transport(path: Path, workspace: Path) -> None:
    """Fail before upstream can skip numeric grading on transport errors."""
    import yaml
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    config = yaml.safe_load(path.read_text())
    params = config['params']
    params['cwd'] = str(workspace)
    params['env'] = {**os.environ, **params.get('env', {})}
    async with asyncio.timeout(config['client_session_timeout_seconds']):
        async with stdio_client(StdioServerParameters(**params)) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                for ticker in ('CL=F', 'BZ=F'):
                    result = await session.call_tool(
                        'get_historical_stock_prices', {
                            'ticker': ticker,
                            'period': '2y',
                            'interval': '1mo'
                        })
                    if result.isError:
                        raise RuntimeError(
                            'Oil numeric grading transport failed')
                    rows = json.loads(result.content[0].text)
                    if not isinstance(rows, list) or not rows or any(
                            row.get('Close') is None for row in rows):
                        raise RuntimeError('Oil numeric grading has no prices')
                    verify_oil_prices(rows)
                    await verify_oil_months(session, ticker, rows,
                                            datetime.now(timezone.utc))


def prepare_evaluator_services(task: str, workspace: Path) -> None:
    """Refresh vulnerable evaluator configs on every grade, not just setup."""
    from server.mcp.mcp_servers import upstream_config
    from setup.toolathlon.setup_toolathlon import (point_howtocook_at_pinned,
                                                   point_yahoo_at_gym)
    configs = dataset.root() / 'configs/mcp_servers'
    if task == 'cooking-guidance':
        point_howtocook_at_pinned(configs / 'howtocook.yaml')
    if task == 'oil-price':
        path = configs / 'yahoo-finance.yaml'
        path.write_text(upstream_config('yahoo-finance'))
        point_yahoo_at_gym(path)
        asyncio.run(verify_oil_transport(path, workspace))


def pg_env() -> dict[str, str]:
    """The fixture DSN, spelled the way the snowflake shim reads it.

    Returns:
        dict[str, str]: the five PG_* variables.
    """
    dsn = urlparse(yf_dsn())
    return {
        "PG_HOST": dsn.hostname or "localhost",
        "PG_PORT": str(dsn.port or 5432),
        "PG_USER": dsn.username or "postgres",
        "PG_PASSWORD": dsn.password or "",
        "PG_DATABASE": (dsn.path or "/").lstrip("/") or "postgres",
    }


def yahoo(task: str) -> tuple[list[Path], dict, list[str]]:
    """A yahoo evaluator prices its own expected answer, live.

    One that imports the SDK calls `yf.Ticker(...)` at grading time, as
    upstream's does, so its reads go through the same recording transport
    as the agent's tools. The rest need nothing: `oil-price` reaches Yahoo
    through the server its config names, and a second `sitecustomize` on
    the path would hide the task's own Notion shim.
    """
    evaluator = UPSTREAM / task / "evaluation"
    if not any("yfinance" in path.read_text()
               for path in evaluator.rglob("*.py")):
        return ([], {}, [])
    return ([REPO_ROOT / "redirect" / "yahoo_capture"], {}, [])


def snowflake(task: str) -> tuple[list[Path], dict, list[str]]:
    """A snowflake evaluator reads the warehouse back at grading time.

    Through `utils/app_specific/snowflake/client.py`, which builds a
    connection from the global token block and cannot be pointed anywhere
    from outside. `redirect/snowflake` shadows the client so it lands on
    the same Postgres the agent wrote to.
    """
    return ([REPO_ROOT / "redirect" / "snowflake"], pg_env(),
            ["--with", "psycopg2-binary==2.9.12"])


def notion(task: str) -> tuple[list[Path], dict, list[str]]:
    """A notion evaluator hardcodes api.notion.com and the global token.

    Neither can be configured from outside, so the task's own `eval_shim`
    rewrites both onto the fake this run seeded.
    """
    token = json.loads((dataset.local(task) / "shared" /
                        "notion.json").read_text())["workspace"]
    return ([dataset.local(task) / "toolathlon" / "eval_shim"], {
        "NOTION_URL": os.environ.get("NOTION_URL", "http://127.0.0.1:5091"),
        "NOTION_TOKEN": token,
    }, [])


def huggingface(task: str) -> tuple[list[Path], dict, list[str]]:
    """A Hub evaluator reads the repository the agent just pushed.

    `HF_ENDPOINT` it honours on its own; the token it takes from upstream's
    `configs/token_key_session.py`, where it is the unfilled "XX". On this
    fake the bearer is the tenant, so grading with that reads an empty Hub
    and reports the repository missing -- an agent failure that is not one.
    """
    return shimmed(
        task, {
            "HF_ENDPOINT": os.environ.get("HF_ENDPOINT",
                                          "http://127.0.0.1:5199"),
            "HF_TOKEN": os.environ.get("HF_TOKEN", task),
        })


def shimmed(task: str, env: dict) -> tuple[list[Path], dict, list[str]]:
    """A redirect that is only wanted where the task ships the shim for it.

    Declaring a server does not mean the evaluator reads it back: `git-repo`
    is graded on a frozen capture, and `nhl-b2b-analysis`'s override reads
    `GWS_URL` out of the ambient environment with a default of its own. Both
    the path and the variable belong to the shim, so where there is no shim
    there is nothing to contribute.

    Args:
        task (str): the task name.
        env (dict): what the shim reads, if it is there.

    Returns:
        tuple: the shim path and its environment, or nothing.
    """
    shim = dataset.local(task) / "toolathlon" / "eval_shim"
    return ([shim], env, []) if shim.is_dir() else ([], {}, [])


def github(task: str) -> tuple[list[Path], dict, list[str]]:
    """A github evaluator reads back the repository the agent just wrote.

    There is nothing to freeze: it has to reach the same live fake.
    `utils/app_specific/github/api.py` hardcodes GITHUB_API, so the host is
    rewritten in the shim.
    """
    return shimmed(task, {
        "GITHUB_URL":
        os.environ.get("GITHUB_URL", "http://127.0.0.1:19801"),
    })


def google_sheet(task: str) -> tuple[list[Path], dict, list[str]]:
    """A sheets evaluator opens the spreadsheet with gspread.

    Whose URLs are googleapis.com string constants bound at import time.
    Same `eval_shim` directory as the notion redirect: only one
    `sitecustomize` is ever imported, so a task needing both loads both from
    its own.
    """
    return shimmed(task, {
        "GWS_MOCK_URL":
        os.environ.get("GWS_URL", "http://127.0.0.1:19999"),
    })


def place_gcp_key() -> None:
    """Put the generated service-account key where an evaluator opens it.

    `server/bq/token_stub.py` writes the key into the stack's shared volume,
    and every reader so far has been told about it: the MCP server takes
    `GCP_SERVICE_ACCOUNT`, and the two emulator variables carry the rest.
    An evaluator that opens `configs/gcp-service_account.keys.json` --
    a bare relative path resolved against the checkout it runs in -- cannot
    be told anything, so what it opens has to be made to exist.

    `flagged-transactions` and `machine-operating` never needed this: their
    evaluators build a client and let `BIGQUERY_EMULATOR_HOST` and
    `STORAGE_EMULATOR_HOST` decide. `ab-testing` is the first that reads the
    file itself, and its failure mode is the reason this is not left to
    chance -- it swallows the credential error and falls back to
    `subprocess.run(['gcloud', ...])`, so a missing key reads as "the agent
    never created the bucket" rather than as a broken harness. Half an hour
    of a correct answer being graded as a total failure.

    Copied rather than symlinked, because the path is inside the pinned
    checkout and a dangling link would outlive the stack that made it. The
    path is in upstream's own `.gitignore`, so the copy does not dirty the
    submodule.
    """
    source = Path(
        os.environ.get(
            "GCP_SERVICE_ACCOUNT",
            REPO_ROOT / "state" / "stack" / "gcp-service_account.keys.json"))
    target = UPSTREAM.parents[1] / "configs" / "gcp-service_account.keys.json"
    if not source.is_file() or not target.parent.is_dir():
        return
    if target.is_file() and target.read_bytes() == source.read_bytes():
        return
    shutil.copyfile(source, target)


def upstream_launch_time(stamped: str) -> str:
    """The seed's timestamp, spelled the way upstream's own runner spells it.

    `utils/data_structures/task_config.py:312` builds it as
    `"%Y-%m-%d %H:%M:%S %A"`, weekday included, and three evaluators parse
    it back with exactly that format. The seed records
    `"%Y-%m-%d %H:%M:%S"` instead, because the same field clocks the
    BigQuery emulator and is read by `bin/start.sh` and `server/api/app.py`
    -- so the weekday is added here, at the one point of use, rather than
    stored and then stripped by three other readers.

    Getting this wrong is quiet, which is why it is worth a function.
    `ab-testing` wraps its whole log check in `except Exception: return
    True`, so an unparseable timestamp does not fail the grade -- it skips
    the check and reports success. The task would be graded on its bucket
    and its CSV while the assertion about log entries silently never ran.

    Non-destructive where it does not apply: a value that already carries a
    weekday, or one that is not a timestamp at all, is handed back
    untouched for the evaluator to reject on its own terms.

    Args:
        stamped (str): the seed's timestamp.

    Returns:
        str: the same instant with the weekday appended, or `stamped`.
    """
    try:
        when = datetime.strptime(stamped.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stamped
    return when.strftime("%Y-%m-%d %H:%M:%S %A")


def google_cloud(task: str) -> tuple[list[Path], dict, list[str]]:
    """Two of the three services honour their own emulator variable.

    Written here rather than left to the ambient shell because the default
    is *the live service*: an unset variable grades against a GCP project
    this repo has no credentials for, which reads as an agent failure and is
    not one. Cloud Logging has no such variable, so it is redirected the way
    the snowflake ones are -- and only where the task has a log fixture,
    since the shim is what decides where a log entry goes.
    """
    place_gcp_key()
    env = {
        "BIGQUERY_EMULATOR_HOST":
        os.environ.get("BIGQUERY_EMULATOR_HOST", "http://127.0.0.1:9051"),
        "STORAGE_EMULATOR_HOST":
        os.environ.get("STORAGE_EMULATOR_HOST", "http://127.0.0.1:9070"),
        # UTC, because that is the timezone upstream's evaluators are
        # correct in. Each of the three that reads a log window bounds it
        # with
        #
        #   datetime.now().astimezone(local).strftime("...T%H:%M:%S+00:00")
        #
        # which prints the *local* clock and then labels it UTC. On a
        # machine that already runs UTC the lie is true and nobody notices;
        # here it puts the upper bound seven hours in the past, so a log
        # entry written seconds ago is outside the window and the query
        # returns nothing.
        #
        # Matching upstream's environment rather than editing upstream's
        # code: the evaluator is authority on what passes, and the only
        # thing wrong is the clock it was handed.
        #
        # This is why `ab-testing` passed before the fix and
        # `live-transactions` did not. ab-testing asserts the window is
        # *empty*, so a window that excludes everything is vacuously
        # satisfied -- it was being graded on a question nobody asked.
        #
        # One asymmetry is left standing. The seed records its timestamp in
        # local time, so under UTC the *lower* bound reads those digits as
        # UTC and lands earlier than the seed really was. It decides
        # nothing: seeding drops every entry in the bucket, so there is
        # nothing older than the seed for a loose floor to admit. Moving
        # what the seed stores would reach `gcp.point_at`, `bin/start.sh`
        # and `server/api/app.py` to fix a bound that no task consults.
        "TZ":
        "UTC",
    }
    if not (dataset.local(task) / "shared" / "logging.json").is_file():
        return ([], env, [])
    base = os.environ.get("API_URL", "http://127.0.0.1:9110").rstrip("/")
    env["CLOUD_LOGGING_API"] = os.environ.get("CLOUD_LOGGING_API",
                                              f"{base}/api/{task}/logging")
    return ([REPO_ROOT / "redirect" / "cloud_logging"], env, [])


# One entry per server whose evaluator has to be redirected, keyed by the
# name upstream spells in task_config.json. A server absent from here needs
# nothing: it either grades a file in the workspace or reaches a fake that
# is already where the client library expects it.
def papers(task):
    return ([REPO_ROOT / "redirect/papers"], {
        "PAPER_API_URL": os.environ["PAPER_API_URL"]
    }, [])


REDIRECTS = {
    "arxiv_local": papers,
    "yahoo-finance": yahoo,
    "snowflake": snowflake,
    "notion": notion,
    "github": github,
    "google_sheet": google_sheet,
    "google-cloud": google_cloud,
    "huggingface": huggingface,
}


def web_capture(task: str) -> tuple[list[Path], dict, list[str]]:
    """A fetch evaluator re-fetches the live web at grading time.

    And scores the agent against a band between that and a snapshot
    committed months ago -- so the band depends on the hour it was graded,
    on the grader having network, and on its rate limit. The agent read a
    capture, so the evaluator reads the same one.

    Keyed off the capture rather than off a server, because a task can carry
    one without needing its grade redirected: only the ones whose evaluator
    actually refetches ship the `eval_shim`.
    """
    fixture = dataset.local(task) / "shared" / "web_fixture.json"
    if not fixture.is_file():
        return ([], {}, [])
    return ([dataset.local(task) / "toolathlon" / "eval_shim"], {
        "WEB_FIXTURE": str(fixture)
    }, [])


def own_shim(task: str) -> tuple[list[Path], dict, list[str]]:
    """The task's own `eval_shim`, for an evaluator no redirect above names.

    `git-milestone` declares `filesystem`, `terminal` and `fetch`, and its
    evaluator refetches api.github.com itself, signing with upstream's
    unfilled token; its shim signs with the operator's. Every other task
    that ships a shim is given it by a redirect above already, so for them
    this adds nothing.
    """
    return ([dataset.local(task) / "toolathlon" / "eval_shim"], {}, [])


def servers(task: str) -> list[str]:
    """The servers upstream declares for one task.

    Args:
        task (str): the task name.

    Returns:
        list[str]: the server names, or empty if there is no config.
    """
    if not dataset.task_dir(task).joinpath(*dataset.CONFIG).is_file():
        return []
    return dataset.needed_mcp_servers(task)


def redirection(task: str) -> tuple[list[str], dict[str, str], list[str]]:
    """Everything one evaluator needs to read fixtures instead of services.

    Args:
        task (str): the task name.

    Returns:
        tuple: the PYTHONPATH entries in order, the environment, and any
            extra `uv run` arguments.
    """
    paths: list[str] = []
    env: dict[str, str] = {}
    extras: list[str] = []
    sources = [REDIRECTS[name] for name in servers(task) if name in REDIRECTS]
    for build in [*sources, web_capture, own_shim]:
        more_paths, more_env, more_extras = build(task)
        for path in more_paths:
            # A shim that does not exist is a task that does not need one:
            # `github` and `google_sheet` both point at the task's own
            # `eval_shim`, which only the tasks that refetch actually ship.
            if path.is_dir() and str(path) not in paths:
                paths.append(str(path))
        env.update(more_env)
        for extra in more_extras:
            if extra not in extras:
                extras.append(extra)
    return paths, env, extras


def combined_shims(paths: list[str], directory: Path) -> list[str]:
    """Put one `sitecustomize` first that runs every shim's, in path order.

    Python imports the first `sitecustomize` on the path and no other, so a
    grader that needs two -- investment-decision-analysis reads Yahoo and
    its sheet -- would otherwise lose the second without a word.

    Args:
        paths (list[str]): the PYTHONPATH entries, in order.
        directory (Path): an empty directory for the combined shim.

    Returns:
        list[str]: the entries to use instead.
    """
    shims = [
        str(Path(path) / "sitecustomize.py") for path in paths
        if (Path(path) / "sitecustomize.py").is_file()
    ]
    if len(shims) < 2:
        return paths
    (directory / "sitecustomize.py").write_text(
        "import importlib.util\n"
        f"for index, path in enumerate({shims!r}):\n"
        "    spec = importlib.util.spec_from_file_location(\n"
        "        f'sitecustomize_{index}', path)\n"
        "    spec.loader.exec_module(importlib.util.module_from_spec(spec))\n")
    return [str(directory), *paths]


def evaluator_sha(task: str) -> str:
    """A digest of the evaluator tree, so parity is recorded not assumed.

    Reproduces exactly what the retired batch script used to compute in
    shell -- `find | sort | xargs shasum -a 256 | shasum -a 256`, two
    spaces between hash and path, paths as `./main.py`. The value is
    printed beside every measured arm, so a digest computed a different way
    would be a different number for the same tree and would quietly stop
    comparing with every result already recorded.

    Args:
        task (str): the task name.

    Returns:
        str: the hex digest.
    """
    import hashlib

    root = UPSTREAM / task / "evaluation"
    changes = subprocess.check_output([
        "git", "-C",
        str(UPSTREAM.parents[1]), "diff", "HEAD", "--",
        str(root.relative_to(UPSTREAM.parents[1]))
    ])
    if changes:
        raise RuntimeError(f"Evaluator differs from pinned upstream: {task}")
    paths = sorted(f"./{path.relative_to(root)}" for path in root.rglob("*")
                   if path.is_file() and "__pycache__" not in path.parts
                   and path.suffix != ".pyc")
    listing = "".join(
        f"{hashlib.sha256((root / name[2:]).read_bytes()).hexdigest()}  "
        f"{name}\n" for name in paths)
    return hashlib.sha256(listing.encode()).hexdigest()


def ground_truth(task: str) -> Path | None:
    """Which ground truth this task is graded against.

    A task that seeds its own fixture writes the matching answer sheet as
    it goes, and that one wins: upstream's committed copy describes the day
    upstream last ran its preprocess against a live warehouse.

    Aliased on import as `generated_truth`, because this function is named
    after the same thing: a bare `from services import ground_truth` would
    be shadowed by the `def` below it, the way a module-level name shadowed
    `dataset.POOL`.

    Args:
        task (str): the task name.

    Returns:
        Path | None: the directory, or None if there is none.
    """
    ours = generated_truth(task)
    theirs = UPSTREAM / task / "groundtruth_workspace"
    if ours.is_dir():
        return ours
    return theirs if theirs.is_dir() else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one task's upstream evaluator, pointed "
        "at this repo's fixtures.")
    parser.add_argument("task")
    parser.add_argument("--agent-workspace", default=None)
    parser.add_argument("--launch-time",
                        default=None,
                        help="frozen once per task by the batch, so a long "
                        "first arm cannot move a time cutoff for the second")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--print-sha",
                        action="store_true",
                        help="print the evaluator tree digest and exit")
    args = parser.parse_args(argv)

    sha = evaluator_sha(args.task)
    if args.print_sha:
        print(sha)
        return 0

    # The arm's own resolver, imported rather than restated: a grader that
    # resolved this differently would score a directory the arm never
    # touched -- an empty tree, graded as a total failure with no error.
    # Restating it is how that bug got here in the first place.
    #
    # `run_agent` passes the flag, so the two orders below are for a grader
    # run by hand: the seed's record first, because a measured run names
    # its workspace after itself and that record is the only thing that
    # knows which one; the bare task slot after, which is where a seed run
    # by hand puts it.
    workspace = (Path(args.agent_workspace).resolve() if args.agent_workspace
                 else (seeded_workspace(args.task)
                       or agent_workspace(dataset.local(args.task))))
    sys.path.insert(0, str(REPO_ROOT))
    from server.seed.business import TASKS, grade
    if args.task in TASKS:
        return grade(args.task, workspace, args.launch_time)
    from server.seed.research_sheets import TASKS as sheet_tasks
    from server.seed.research_sheets import grade as sheet_grade
    if args.task in sheet_tasks:
        return sheet_grade(args.task, workspace,
                           upstream_launch_time(args.launch_time or ''),
                           args.timeout)
    from server.seed.final_batch import TASKS as final_tasks
    from server.seed.final_batch import grade as final_grade
    if args.task in final_tasks:
        return final_grade(args.task, workspace,
                           upstream_launch_time(args.launch_time or ''),
                           args.timeout)
    from server.shared_workspace import active
    remote = active()
    if remote and args.task in {'k8s-mysql', 'k8s-pr-preview-testing'}:
        return remote.grade(args.task,
                            upstream_launch_time(args.launch_time or ''),
                            args.timeout)
    if args.task == 'shopping-helper':
        from server.seed.browser import grade as browser_grade
        return browser_grade(args.task, workspace,
                             upstream_launch_time(args.launch_time or ''),
                             args.timeout)
    paths, env, extras = redirection(args.task)
    prepare_evaluator_services(args.task, workspace)

    # res_log is read but never scored by any task here; a stub keeps the
    # ones that read it unconditionally from dying on None.
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                     delete=False) as stub:
        stub.write('{"status": "success", "key_statistics": '
                   '{"tool_calls": 10}}')
        res_log = stub.name

    argv = ["--agent_workspace", str(workspace), "--res_log_file", res_log]
    truth = ground_truth(args.task)
    kept = {}
    if truth is not None:
        argv += ["--groundtruth_workspace", str(truth)]
        # `git-milestone`'s evaluator writes the counts it refetched into
        # `after_task.json` beside the ones upstream committed, which is
        # upstream's behaviour and harmless to this grade -- it never reads
        # the file back -- but leaves the checkout with bytes that are no
        # longer upstream's. They are put back once it exits.
        kept = {
            path: path.read_bytes()
            for path in truth.rglob("*") if path.is_file()
        }
    # This evaluator defaults to the checkout-wide `tmp/` directory. The
    # Hugging Face client deliberately returns an existing local checkout
    # when a remote download fails, so reusing that directory can grade the
    # previous arm's repository after the current arm receives a 404.
    # Upstream already exposes `--download-dir`; give every grade a fresh
    # one, matching the isolated environment in which the task is run.
    download_dir = None
    if args.task == "huggingface-upload":
        download_dir = Path(tempfile.mkdtemp(prefix="hf-upload-grade-"))
        argv += ["--download-dir", str(download_dir)]
    # Passed whenever there is one, as upstream's own driver passes it.
    # Every evaluator in this pool declares it but `price-comparison`, and
    # that one parses no arguments at all, so there is nothing to guard
    # against. Some require it and then ignore the value, reading the
    # warehouse's own clock instead.
    if args.launch_time:
        argv += ["--launch_time", upstream_launch_time(args.launch_time)]

    shim_dir = Path(tempfile.mkdtemp(prefix="grade-shims-"))
    paths = combined_shims(paths, shim_dir)
    if paths:
        env["PYTHONPATH"] = ":".join(paths)
    # Toolathlon runs evaluators as modules (utils/data_structures/
    # task_config.py: `uv run -m ...`), and they use relative imports, so a
    # plain `python path/to/main.py` fails.
    prefix, cwd = dataset.evaluator_argv(args.task)
    try:
        done = subprocess.run(
            [
                "timeout",
                str(args.timeout), *prefix[:2], *extras, *prefix[2:], *argv
            ],
            cwd=cwd,
            env={
                **os.environ,
                **env
            },
        )
    finally:
        Path(res_log).unlink(missing_ok=True)
        shutil.rmtree(shim_dir, ignore_errors=True)
        if download_dir is not None:
            shutil.rmtree(download_dir, ignore_errors=True)
        for path, data in kept.items():
            if not path.is_file() or path.read_bytes() != data:
                path.write_bytes(data)
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
