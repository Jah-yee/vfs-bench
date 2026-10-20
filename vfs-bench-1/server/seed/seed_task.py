#!/usr/bin/env python
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

sys.path.insert(0, str(REPO_ROOT / "agent"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "fakes"))
# Where a task's two halves live comes from the seam, not from a path
# spelled here. This file used to sit inside `task/toolathlon/` and name
# that directory anyway, which is exactly what the seam exists to stop --
# and why a second dataset meant editing the seeder.
import dataset  # noqa: E402
# Imported and called, not spawned. Every one is a sibling in this directory
# running on the project's own dependencies, so `uv run python <path>` bought
# nothing and cost an interpreter start and a uv resolution per fixture --
# and swallowed the traceback, leaving an exit code where the reason had
# been. A task's own seeder still gets a subprocess, and for a reason: it is
# arbitrary code that may declare dependencies this project does not carry.
#
# Aliased, every one, because the dispatch functions below are named after
# the fixture kinds: a bare `import seed_logging` would be shadowed by the
# `def seed_logging` that follows it, the way a module-level name shadowed
# `dataset.POOL`.
import gcp  # noqa: E402
import mail_folders as folders  # noqa: E402
import seed_gcs as gcs  # noqa: E402
import seed_logging as logs  # noqa: E402
import seed_mail as mail  # noqa: E402
import stack  # noqa: E402
from services import empty_workspace, load_stack_env, seed_record  # noqa: E402

# Which `shared/` file makes a fixture of each service kind necessary. Used
# by --check to catch a manifest that has drifted from the tree: a task that
# grew a `storage.json` and no matching entry would silently stop having its
# bucket emptied between arms, which is exactly the failure this file exists
# to prevent.
EVIDENCE = {
    "bigquery": "shared/bigquery.json",
    "storage": "shared/storage.json",
    "logging": "shared/logging.json",
}


def task_id(task: str) -> str:
    """The qualified id for one task directory.

    The dataset is named in the id rather than left implicit, and its name
    is asked of the seam rather than spelled here -- this file used to
    carry its own `DATASET = "toolathlon"` beside the seam's `NAME`, which
    is two spellings of one fact. The directory name stays bare: it is what
    every path, every `--task` flag and every upstream lookup already uses.

    Args:
        task (str): the directory name.

    Returns:
        str: `<dataset>_<task>`.
    """
    return f"{dataset.NAME}_{task}"


def manifest(task: str) -> dict:
    """Read one task's fixture manifest.

    Args:
        task (str): the task name.

    Returns:
        dict: the parsed manifest, or an empty one for a task with no
            fixtures -- most tasks have none, and that is not an error.
    """
    path = dataset.manifest(task)
    if not path.is_file():
        return {"id": task_id(task), "fixtures": []}
    return json.loads(path.read_text(encoding="utf-8"))


def wipe_workspace(task: str) -> Path:
    """Empty the agent workspace, before anything seeds into it.

    The workspace is a fixture like the rest -- four tasks' seeders write
    their starting files straight into it -- so it is emptied here, where
    the fixtures are rebuilt, rather than by each caller in turn. A file
    the previous arm wrote and this one did not is graded as this arm's
    work, and a run set up by hand had no one emptying it at all.

    Args:
        task (str): the task name.

    Returns:
        Path: the emptied workspace.
    """
    workspace = empty_workspace(dataset.local(task))
    # Into the environment, so a task's own seeder inherits the answer rather
    # than working one out -- four of them write their starting files into
    # the workspace, and they run as subprocesses of this one. `main` names
    # it in the seed's record as well, because a measured run names its
    # workspace after itself, and a grader invoked by hand has no other way
    # to find which directory this seed actually filled.
    os.environ["AGENT_WORKSPACE"] = str(workspace)
    return workspace


def run(argv: list[str], what: str) -> None:
    """Run one seeding step as a program, or stop the whole thing.

    One caller left: a task's own seeder, which is arbitrary code and may
    name dependencies through `with` that this project does not carry.
    Everything else is a sibling module and is imported instead, by `step`.

    Args:
        argv (list[str]): the command.
        what (str): the fixture id, for the failure message.

    Raises:
        SystemExit: the step failed.
    """
    done = subprocess.run(argv, cwd=REPO_ROOT)
    if done.returncode != 0:
        raise SystemExit(f"seed_task: {what} failed (exit "
                         f"{done.returncode}); the arm would have run "
                         f"against whatever state was left behind")


def seeded_at(task: str) -> str:
    """When this seed started, from the record `main` wrote.

    Args:
        task (str): the task name.

    Returns:
        str: the timestamp every fixture of this seed is named after.
    """
    record = seed_record(dataset.local(task))
    return json.loads(record.read_text(encoding="utf-8"))["seeded_at"]


def step(work, what: str, *args, **kwargs):
    """Run one seeding step in this process, or stop the whole thing.

    The counterpart of `run` for a step that is a function rather than a
    program. It keeps `run`'s contract -- a failure stops the seed rather
    than letting an arm start against half a fixture -- while letting the
    traceback through, which is the thing the subprocess form threw away.

    Args:
        work (Callable): the seeding function.
        what (str): the fixture id, for the failure message.
        *args: passed to `work`.
        **kwargs: passed to `work`.

    Returns:
        object: whatever `work` returned.

    Raises:
        SystemExit: the step raised.
    """
    try:
        return work(*args, **kwargs)
    except SystemExit:
        raise
    except Exception as raised:
        raise SystemExit(f"seed_task: {what} failed ({type(raised).__name__}: "
                         f"{raised}); the arm would have run against "
                         f"whatever state was left behind") from raised


def empty_mailbox(what: str) -> None:
    """Drop every message GreenMail is holding.

    Inline rather than a script, because that is all it ever was: the
    `bin/start_mail.sh` this used to shell out to spent its `reset` branch
    on exactly this request, and its other two branches ran a GreenMail
    container of its own that collided with the one `docker/compose.yml`
    already defines.

    Args:
        what (str): the fixture id, for the failure message.

    Raises:
        SystemExit: GreenMail refused or is not running.
    """
    port = os.environ.get("MAIL_API_PORT", "8081")
    url = f"http://127.0.0.1:{port}/api/service/reset"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="POST"),
                                    timeout=30) as reply:
            if reply.status != 200:
                raise SystemExit(f"seed_task: {what} failed (GreenMail "
                                 f"answered {reply.status} to {url})")
    except (urllib.error.URLError, OSError) as raised:
        raise SystemExit(
            f"seed_task: {what} failed (no GreenMail at {url}: "
            f"{raised}); start it with bin/start.sh up") from raised


def mail_fixture(task: str) -> Path | None:
    """Resolve the exact inbox imported by the original preprocessing.

    Most original tasks ship ``files/emails_backup.json`` directly. One
    regenerates ``files/importable_emails.json`` before importing it. Its
    DVC fixture runs the pinned formatter against the original JSONL,
    placeholders and checked-in date, and is verified again before seeding.

    Args:
        task (str): the task name.

    Returns:
        Path | None: the fixture to append, or None for an intentionally
            empty mailbox or one populated by a later script fixture.

    Raises:
        ValueError: a derived importable fixture is missing or has drifted.
    """
    task_root = dataset.task_dir(task)
    backup = task_root / "files" / "emails_backup.json"
    if backup.is_file():
        return backup

    if task == "course-assistant":
        return task_root / "files" / "emails.jsonl"

    source = task_root / "files" / "importable_emails.json"
    if not source.is_file():
        return None
    derived = dataset.local(task) / "shared" / "importable_emails.json"
    if not derived.is_file():
        raise ValueError(f"{derived.relative_to(REPO_ROOT)} is missing; "
                         "reproduce its DVC stage")
    if task == "email-paper-homepage":
        import importlib.util
        builder = derived.with_name("derive_mail.py")
        spec = importlib.util.spec_from_file_location("homepage_mail", builder)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if json.loads(derived.read_text()) != module.build():
            raise ValueError(
                "Homepage mail differs from upstream preprocessing")
        return derived
    if derived.read_bytes() != source.read_bytes():
        raise ValueError(f"{derived.relative_to(REPO_ROOT)} differs from "
                         "the pinned upstream import fixture")
    return derived


def seed_mail(task: str, entry: dict) -> None:
    """Reset the mailbox, restore its folders, and put the fixture back.

    Three steps, and all three matter. GreenMail gives a new mailbox an
    INBOX and nothing else where poste.io ships Sent, Drafts and Trash too,
    so a grader that opens one of those crashes rather than failing, and a
    model that sends mail has no Sent for the copy the server keeps. And a
    task whose fixture *is* the inbox has to have it put back after the
    reset, or the arm is graded on an empty mailbox --
    `emails_config.json`'s is the mailbox both arms mount,
    `receiver_config.json`'s is the one the agent's reply is sent to, which
    is created empty so the send has somewhere to land.

    Args:
        task (str): the task name.
        entry (dict): the fixture entry.
    """
    empty_mailbox(entry["id"])
    listing = dataset.task_dir(task) / "files" / "involved_emails.json"
    if listing.is_file():
        step(folders.provision_all, entry["id"], listing)
    # The model's own mailbox gets them whether or not a listing or a fixture
    # would: landing-task-reminder has neither.
    mailbox = dataset.local(task) / "shared" / "emails_config.json"
    if mailbox.is_file():
        step(folders.provision, entry["id"], json.loads(mailbox.read_text()))
    # Guarded on the fixture so it fires only where upstream imports one;
    # the other email tasks inject their own mail from a later `script`
    # fixture or intentionally begin empty.
    fixture = step(mail_fixture, entry["id"], task)
    if fixture is None:
        return
    if not mailbox.is_file():
        raise SystemExit(f"seed_task: {entry['id']} has {fixture} but no "
                         f"mailbox config at {mailbox}")
    receiver = dataset.local(task) / "shared" / "receiver_config.json"
    # `do_reset=False`: `empty_mailbox` above already emptied GreenMail, and
    # a second reset here would drop the folders just provisioned.
    step(mail.fill,
         entry["id"],
         mailbox,
         fixture, [receiver] if receiver.is_file() else [],
         do_reset=False)


def seed_bigquery(task: str, entry: dict) -> None:
    """Give the emulator this task's fixture, starting it if need be.

    A fixture that declares a service brings that service up. Starting a
    task is not the place to know which servers a task wants -- the
    manifest already says, and this is where the manifest is read.

    The emulator takes its fixture as a launch argument, so this recreates
    the container rather than editing it in place. That also makes the
    reset a real one: the sweep it replaced only dropped tables the
    manifest did not name, so a fixture row the previous arm *edited*
    survived into the next arm's draw.

    Args:
        task (str): the task name.
        entry (dict): the fixture entry.
    """
    step(gcp.point_at, entry["id"], task, seeded_at(task))


def seed_storage(task: str, entry: dict) -> None:
    """Recreate the buckets, empty.

    Args:
        task (str): the task name.
        entry (dict): the fixture entry.
    """
    step(gcs.recreate_buckets, entry["id"], task)


def seed_logging(task: str, entry: dict) -> None:
    """Create the log buckets and drop every entry in them.

    Args:
        task (str): the task name.
        entry (dict): the fixture entry.
    """
    step(logs.fill, entry["id"], task)


def seed_script(task: str, entry: dict) -> None:
    """Run the task's own seeder.

    Args:
        task (str): the task name.
        entry (dict): the fixture entry; `run` is the script, relative to
            the task directory, and `with` names any dependency it needs
            that the project does not carry.
    """
    script = dataset.local(task) / entry["run"]
    if not script.is_file():
        raise SystemExit(f"seed_task: {entry['id']} names {entry['run']}, "
                         f"which does not exist")
    extras = []
    for package in entry.get("with", []):
        extras += ["--with", package]
    run(["uv", "run", *extras, "python", str(script)], entry["id"])


KINDS = {
    "mail": seed_mail,
    "bigquery": seed_bigquery,
    "storage": seed_storage,
    "logging": seed_logging,
    "script": seed_script,
}


def check(task: str, spec: dict) -> list[str]:
    """Complaints about one manifest, without building anything.

    Args:
        task (str): the task name.
        spec (dict): the parsed manifest.

    Returns:
        list[str]: one line per problem, empty when the manifest agrees
            with the tree.
    """
    problems = []
    # Nothing reads the manifest's own id -- the directory name is the key
    # everywhere -- so it is checked rather than trusted, on the principle
    # that a label no code consults is a label that drifts.
    if spec.get("id") != task_id(task):
        problems.append(f"id is {spec.get('id')!r}, expected "
                        f"{task_id(task)!r}")
    seen = set()
    for entry in spec["fixtures"]:
        if entry["kind"] not in KINDS:
            problems.append(f"{entry['id']}: unknown kind {entry['kind']!r}")
        if entry["id"] in seen:
            problems.append(f"{entry['id']}: listed twice")
        seen.add(entry["id"])
        seen.add(entry["kind"])
        if entry["kind"] == "script":
            if "run" not in entry:
                problems.append(f"{entry['id']}: a script fixture needs `run`")
            elif not (dataset.local(task) / entry["run"]).is_file():
                problems.append(f"{entry['id']}: {entry['run']} is missing")
        elif entry["kind"] == "mail":
            try:
                mail_fixture(task)
            except ValueError as raised:
                problems.append(f"{entry['id']}: {raised}")
    for kind, evidence in EVIDENCE.items():
        if (dataset.local(task) / evidence).exists() and kind not in seen:
            problems.append(f"{evidence} exists but no {kind} fixture is "
                            f"declared; it would not be reset between arms")
    for name in ("seed_db.py", "seed_mock.py", "seed_github.py",
                 "seed_notion.py"):
        path = dataset.local(task) / "shared" / name
        declared = any(
            entry.get("run") == f"shared/{name}" for entry in spec["fixtures"])
        if path.is_file() and not declared:
            problems.append(f"shared/{name} exists but no fixture runs it")
    config = dataset.task_dir(task) / "task_config.json"
    if config.is_file():
        servers = json.loads(config.read_text())["needed_mcp_servers"]
        # This check protects the mailbox in the shared local stack. A task
        # whose dataset owns a per-run service never reaches that stack:
        # Canvas/WooCommerce and the remaining research tasks create
        # isolated mailboxes inside services(). Requiring a shared-stack
        # manifest entry for those tasks reports drift where none exists
        # and would describe the wrong reset path.
        decide = getattr(dataset, "needs_stack", None)
        shared_stack = decide(task) if decide else True
        if shared_stack and "emails" in servers and "mail" not in seen:
            problems.append("the task declares the emails server but no mail "
                            "fixture; the mailbox would carry over")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Put one task's fixtures back to their "
        "starting state, in order.")
    parser.add_argument("task")
    parser.add_argument("--check",
                        action="store_true",
                        help="report drift between the manifest and the "
                        "tree, and build nothing")
    args = parser.parse_args(argv)

    # The stack's addresses, so a seed works without anyone having run
    # `eval "$(bin/start.sh env)"` first. `seed_gcs` refuses to run without
    # `STORAGE_EMULATOR_HOST` rather than reach the real Cloud Storage, and
    # being told to seed is not a reason to have been told the endpoints.
    load_stack_env()

    # One reading, for every task and not just the BigQuery ones: the seed
    # is the moment this task's fixtures came into existence, so it is what
    # the evaluator's `--launch-time` means. Written before anything is
    # built, so a slow seed cannot move it, and handed to the emulator so a
    # generated answer table is named after the same instant.
    seeded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    spec = manifest(args.task)
    if args.check:
        problems = check(args.task, spec)
        for line in problems:
            print(f"{args.task}: {line}", file=sys.stderr)
        return 1 if problems else 0

    workspace = wipe_workspace(args.task)
    print(f"workspace: {workspace} emptied", flush=True)
    seed_record(dataset.local(args.task)).write_text(
        json.dumps(
            {
                "task": args.task,
                "seeded_at": seeded_at,
                "workspace": str(workspace)
            },
            indent=2) + "\n")
    # Every fake this task uses, and before anything is built. What a task's
    # manifest cannot restore is state the *previous* draw left in one of
    # them; emptying first is what makes the starting state a property of
    # the task rather than of the run before it. Only those: the others may
    # be another draw's, running beside this one, and it holds them.
    decide = getattr(dataset, "needs_stack", None)
    needs_stack = decide(args.task) if decide else True
    uses = stack.used(args.task)
    # Standalone services use the dataset's per-arm lifecycle instead.
    if needs_stack:
        stack.up(uses)
        stack.reset(args.task, uses)
    # Before the fixtures, and not conditional on one: an emulator the
    # *previous* draw loaded would otherwise still hold its tables, and
    # the emulator's record would keep publishing its `BQ_LAUNCH_TIME` --
    # the evaluator's idea of which answer table to go looking for. Only a
    # task that reaches the emulator takes it down; any other draw's use of
    # it is that draw's business.
    if "gcp" in uses and not any(e["kind"] == "bigquery"
                                 for e in spec["fixtures"]):
        gcp.stop(f"{args.task} declares no bigquery fixture")
    for entry in spec["fixtures"]:
        build = KINDS.get(entry["kind"])
        if build is None:
            raise SystemExit(f"seed_task: no builder for kind "
                             f"{entry['kind']!r} ({entry['id']})")
        print(f"fixture: {entry['id']}", flush=True)
        build(args.task, entry)
    if spec["fixtures"]:
        print(f"seed_task: {args.task}, "
              f"{len(spec['fixtures'])} fixture(s) rebuilt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
