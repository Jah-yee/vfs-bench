#!/usr/bin/env python
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
LOCAL = REPO_ROOT / "task" / "toolathlon"
SUB = REPO_ROOT / "submodule" / "Toolathlon"
UPSTREAM_REL = "tasks/finalpool/{task}/docs/task.md"


def upstream(task: str) -> bytes:
    """One task's ask, read from the pinned commit rather than off disk.

    `setup/toolathlon/setup_toolathlon.py` rewrites files inside the
    submodule, so the working tree is partly our own edits. `docs/task.md`
    is not one of them today, and reading it through `git show` is what
    keeps that true by construction rather than by memory.

    Args:
        task (str): the task name.

    Returns:
        bytes: upstream's file.

    Raises:
        SystemExit: upstream has no such task.
    """
    found = subprocess.run([
        "git", "-C",
        str(SUB), "show", f"HEAD:{UPSTREAM_REL.format(task=task)}"
    ],
                           capture_output=True,
                           check=False)
    if found.returncode != 0:
        raise SystemExit(
            f"derive_task_md: upstream has no {task}/docs/task.md")
    return found.stdout


# The derivation is a byte-for-byte copy, and deliberately nothing else.
# `.pre-commit-config.yaml` excludes `shared/task.md` from the whitespace
# hooks for the same reason: the ask is what the model is sent, so stripping
# a trailing space from it is a change to the measurement, not tidying.
#
# Nine of the asks had been normalised anyway, before that exclusion existed
# -- trailing spaces and a final newline gone. Re-deriving puts upstream's
# bytes back, which is what `--check` will hold them to from here.


def tasks() -> list[str]:
    """Every task directory that has an ask.

    `script/` and `shared/` sit beside the tasks rather than under them,
    and used to be told apart by a leading underscore. What distinguishes
    a task is that it has an ask, so that is what this asks -- which is
    also true of a task directory that is only half built, and says so by
    being absent from the list.

    Returns:
        list[str]: task names, sorted.
    """
    return sorted(d.name for d in LOCAL.iterdir()
                  if d.is_dir() and (d / "shared" / "task.md").is_file())


def main() -> int:
    """Copy each named task's ask from upstream, or check they match.

    Args:
        argv[1:]: task names, or none for all; `--check` compares without
            writing and reports what drifted.

    Returns:
        int: 0, or 1 if `--check` found a difference.
    """
    argv = sys.argv[1:]
    check = "--check" in argv
    wanted = [a for a in argv if not a.startswith("-")] or tasks()

    drifted = []
    for task in wanted:
        want = upstream(task)
        path = LOCAL / task / "shared" / "task.md"
        if path.is_file() and path.read_bytes() == want:
            continue
        drifted.append(task)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(want)

    if check:
        for task in drifted:
            print(f"drifted from upstream: {task}/shared/task.md")
        print(f"derive_task_md --check: {len(wanted) - len(drifted)}"
              f"/{len(wanted)} match upstream")
        return 1 if drifted else 0
    print(f"derive_task_md: {len(wanted)} ask(s), {len(drifted)} rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
