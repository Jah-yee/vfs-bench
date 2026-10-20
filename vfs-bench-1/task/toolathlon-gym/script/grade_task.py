#!/usr/bin/env python
import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "task"))
sys.path.insert(0, str(REPO_ROOT / "agent"))

import dataset  # noqa: E402

# This script lives inside the dataset it serves, so it names it from its own
# path rather than inheriting whatever the caller happened to have loaded.
dataset.use(Path(__file__).resolve().parents[1].name)

from services import agent_workspace  # noqa: E402
from services import seeded_workspace  # noqa: E402

# No redirects. Toolathlon's grader carries six, because six of its
# evaluators reach a live service at grading time and have to be pointed at a
# fake instead. A GYM evaluator reaches its own Postgres, and the one task
# ported here reaches nothing at all: it opens two files in the workspace and
# checks their structure. The first task here that declares `snowflake` will
# need the same treatment as Toolathlon's, and this is the file it goes in.


def evaluator_sha(task: str) -> str:
    """A digest of the evaluator tree, so parity is recorded not assumed.

    The same computation Toolathlon's grader does -- per-file sha256, two
    spaces, `./`-relative paths, then a sha256 of that listing -- because
    the value is printed beside every measured arm and a digest computed a
    different way would quietly stop comparing with every result already
    recorded.

    Args:
        task (str): the task name.

    Returns:
        str: the hex digest.
    """
    root = dataset.evaluator(task).parent
    paths = sorted(f"./{path.relative_to(root)}" for path in root.rglob("*")
                   if path.is_file() and "__pycache__" not in path.parts
                   and path.suffix != ".pyc")
    listing = "".join(
        f"{hashlib.sha256((root / name[2:]).read_bytes()).hexdigest()}  "
        f"{name}\n" for name in paths)
    return hashlib.sha256(listing.encode()).hexdigest()


def main(argv=None) -> int:
    """Run one task's upstream evaluator against what the arm left behind.

    Returns:
        int: the evaluator's exit status.
    """
    parser = argparse.ArgumentParser(
        description="Run one GYM task's own evaluator.")
    parser.add_argument("task")
    parser.add_argument("--agent-workspace", default=None)
    parser.add_argument("--launch-time",
                        default=None,
                        help="frozen once per task by the seed, so a long "
                        "first arm cannot move a cutoff for the second")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--print-sha",
                        action="store_true",
                        help="print the evaluator tree digest and exit")
    args = parser.parse_args(argv)

    if args.print_sha:
        print(evaluator_sha(args.task))
        return 0

    # The arm's own resolver, imported rather than restated: a grader that
    # resolved this differently would score a directory the arm never
    # touched -- an empty tree, graded as a total failure with no error.
    workspace = (Path(args.agent_workspace).resolve() if args.agent_workspace
                 else (seeded_workspace(args.task)
                       or agent_workspace(dataset.local(args.task))))

    # Read but never scored by anything here; a stub keeps the evaluators
    # that read it unconditionally from dying on None.
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                     delete=False) as stub:
        stub.write('{"status": "success", "key_statistics": '
                   '{"tool_calls": 10}}')
        res_log = stub.name

    argv = ["--agent_workspace", str(workspace), "--res_log_file", res_log]
    truth = dataset.groundtruth(args.task)
    if truth.is_dir():
        argv += ["--groundtruth_workspace", str(truth)]
    # Only where the evaluator names it: the others reject an unknown flag.
    if args.launch_time and "launch_time" in dataset.evaluator(
            args.task).read_text():
        argv += ["--launch_time", args.launch_time]

    prefix, cwd = dataset.evaluator_argv(args.task)
    done = subprocess.run(
        ["timeout", str(args.timeout), *prefix, *argv],
        cwd=cwd,
        env=os.environ.copy())
    Path(res_log).unlink(missing_ok=True)
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
