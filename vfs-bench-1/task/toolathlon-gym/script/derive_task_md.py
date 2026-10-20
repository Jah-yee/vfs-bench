#!/usr/bin/env python
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
LOCAL = REPO_ROOT / "task" / "toolathlon-gym"
SUB = REPO_ROOT / "submodule" / "toolathlon_gym"
UPSTREAM_REL = "tasks/finalpool/{task}/docs/task.md"


def upstream(task: str) -> bytes:
    """One task's ask, read from the pinned commit rather than off disk.

    Through `git show` for the reason the other datasets read that way: a
    checkout can be left on some other commit, or edited by a setup script,
    and this file is handed to both arms verbatim -- so a working tree that
    has drifted would change the measurement with nothing to show for it.

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
            f"derive_task_md: {SUB.name} has no {task}/docs/task.md at its "
            f"pinned commit")
    return found.stdout


# A byte-for-byte copy and deliberately nothing else.
# `.pre-commit-config.yaml` already excludes `task/*/*/shared/task.md` from
# the whitespace hooks, for this dataset as much as the other two: the ask is
# what the model is sent, so stripping a trailing space from it is a change to
# the measurement rather than tidying.


def tasks() -> list[str]:
    """Every task directory that has an ask.

    `script/` sits beside the tasks rather than under them, and what tells a
    task from it is that a task has an ask -- which is also true of a task
    directory that is only half built, and which says so by being absent.

    Returns:
        list[str]: task names, sorted.
    """
    return sorted(d.name for d in LOCAL.iterdir()
                  if d.is_dir() and (d / "shared" / "task.md").is_file())


def main() -> int:
    """Copy each named task's ask from upstream, or check they match.

    Args:
        None.

    Returns:
        int: 0 when every ask matches the pinned commit.
    """
    argv = sys.argv[1:]
    checking = "--check" in argv
    wanted = [a for a in argv if not a.startswith("--")] or tasks()

    failed = 0
    for task in wanted:
        want = upstream(task)
        into = LOCAL / task / "shared" / "task.md"
        if checking:
            got = into.read_bytes() if into.is_file() else b""
            if got != want:
                print(f"differs: {into.relative_to(REPO_ROOT)}")
                failed += 1
            continue
        into.parent.mkdir(parents=True, exist_ok=True)
        into.write_bytes(want)
        print(f"{task}: {len(want)} bytes from {SUB.name}")
    if failed:
        print(f"{failed} ask(s) differ from upstream", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
