#!/usr/bin/env python
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "task"))
sys.path.insert(0, str(REPO_ROOT / "agent"))

import dataset  # noqa: E402

# This script lives inside the dataset it serves, so it names it from its own
# path rather than inheriting whatever the caller happened to have loaded.
# `grading.child_env` sets BENCH_DATASET for the children *it* spawns, but dvc
# and a bare shell do not, and the default would quietly be another dataset.
dataset.use(Path(__file__).resolve().parents[1].name)

from services import empty_workspace, seed_record  # noqa: E402

# `task_agent.py:165` makes these three before the run, one per server that
# writes into a directory of its own rather than into the workspace root. No
# task ported here declares any of them yet; reproduced anyway because the
# first one that does would otherwise fail on a missing directory rather than
# on anything it did.
SERVER_DIRS = {
    "arxiv_local": "arxiv_local_storage",
    "memory": "memory",
    "playwright_with_chunk": ".playwright_output",
}


def wipe(task: str) -> Path:
    """Empty the agent workspace, before the task's own setup fills it.

    Both arms run one after the other against the same directory name, so a
    workspace left as the previous arm finished with it is the previous
    arm's answer sitting in front of this one -- and this task is graded on
    two files it is asked to create, which is exactly the shape that would
    pass by inheritance.

    Args:
        task (str): the task name.

    Returns:
        Path: the emptied workspace.
    """
    return empty_workspace(dataset.local(task))


def preprocess(task: str, workspace: Path, launch_time: str) -> int:
    """Run the task's own setup script, the way GYM runs it.

    `task_config.py:76` builds `{python_bin} -m tasks.finalpool.<task>.
    preprocess.main` and `task_agent.py:172` appends the two arguments, so
    that is what this spells. A subprocess and not an import, which is the
    one case this repo allows: the callee is upstream's code, written
    against upstream's interpreter and upstream's dependency set, and it is
    run as a module because it is one.

    Args:
        task (str): the task name.
        workspace (Path): the emptied agent workspace.
        launch_time (str): `YYYY-MM-DD HH:MM:SS`, no weekday.

    Returns:
        int: the script's exit status.
    """
    script = dataset.preprocess(task)
    if not script.is_file():
        print(f"seed_task: {task} ships no preprocess/main.py")
        return 0
    module = ".".join(
        (*dataset.POOL, task, *dataset.PREPROCESS)).removesuffix(".main.py")
    done = subprocess.run([
        "uv", "run", "-m", f"{module}.main", "--agent_workspace",
        str(workspace), "--launch_time", launch_time
    ],
                          cwd=dataset.root())
    return done.returncode


def main(argv=None) -> int:
    """Put one task's fixtures back to their starting state.

    Which for GYM means an empty workspace and whatever the task's own
    `preprocess/main.py` then does to it. The 321 tasks that ship an
    `initial_workspace/` are not copied here: `arms.build_workspace_dir`
    does that for every dataset, and doing it twice would mean two places
    that decide what a run starts from.

    Returns:
        int: 0 when the task is ready to draw.
    """
    parser = argparse.ArgumentParser(
        description="Empty one task's workspace and run its own setup.")
    parser.add_argument("task")
    parser.add_argument("--check",
                        action="store_true",
                        help="report what a draw would start from, without "
                        "emptying or running anything")
    args = parser.parse_args(argv)

    manifest = dataset.manifest(args.task)
    if not manifest.is_file():
        print(f"seed_task: no manifest at {manifest}", file=sys.stderr)
        return 1
    spec = json.loads(manifest.read_text())
    expected = f"{dataset.NAME}_{args.task}"
    if spec.get("id") != expected:
        print(
            f"seed_task: manifest id is {spec.get('id')!r}, expected "
            f"{expected!r}",
            file=sys.stderr)
        return 1

    servers = dataset.needed_mcp_servers(args.task)
    missing = [name for name in servers if name not in dataset.SERVERS]
    if missing:
        print(
            f"seed_task: {args.task} declares {missing}, which this "
            f"dataset has no builder for",
            file=sys.stderr)
        return 1

    if args.check:
        print(f"servers: {', '.join(servers)}")
        print(
            f"stack:   {'needed' if dataset.needs_stack(args.task) else 'no'}")
        print(f"setup:   {dataset.preprocess(args.task)}")
        return 0

    workspace = wipe(args.task)
    print(f"workspace: {workspace} emptied", flush=True)
    for name in servers:
        if name in SERVER_DIRS:
            (workspace / SERVER_DIRS[name]).mkdir(parents=True, exist_ok=True)
            print(f"  made {SERVER_DIRS[name]}/ for {name}")

    launch_time = time.strftime("%Y-%m-%d %H:%M:%S")
    failed = preprocess(args.task, workspace, launch_time)
    if failed:
        print(f"seed_task: preprocess exited {failed}", file=sys.stderr)
        return failed

    # The same record Toolathlon's seeder writes, because the same two
    # readers read it: `grading.seeded_at` takes the launch time the
    # evaluator is given, and `services.seeded_workspace` is how a grader
    # run by hand finds the directory a measured run named after itself.
    seed_record(dataset.local(args.task)).write_text(
        json.dumps(
            {
                "task": args.task,
                "seeded_at": launch_time,
                "workspace": str(workspace)
            },
            indent=2) + "\n")
    print(f"ready: {args.task} ({len(servers)} servers, "
          f"{len(dataset.needed_local_tools(args.task))} local tools "
          f"declared)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
