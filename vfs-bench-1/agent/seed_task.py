"""Seed one task's fixtures the way a run does, for `bin/start.sh task`.

The shell command used to call the Toolathlon seeder by path, which is
the one fact about a dataset that belongs inside its seam: half the
tasks here are MCP-Atlas's, and Toolathlon-GYM seeds by preprocessing
rather than through `server/seed/seed_task.py`. Read the task the way
`run_agent.py` reads its argument -- `dataset.split`, with its
one-dataset-or-say-which rule -- and hand it to `grading.seed`, which
selects the seam's own seeder and its environment. What
`bin/start.sh task` prepares is then what a run starts from, for every
dataset the checkout carries, and the shell script spells no dataset.
"""
import argparse

import dataset
from grading import seed
from services import REPO_ROOT


def main(argv=None) -> int:
    """Rebuild one task's fixtures, whatever dataset carries it.

    Args:
        argv (list[str] | None): the command line, for testing.

    Returns:
        int: the seeder's exit status.
    """
    parser = argparse.ArgumentParser(
        description="Rebuild one task's fixtures, selecting the dataset's "
        "own seeder.")
    parser.add_argument(
        "task",
        help="the task to seed: <dataset>/<task>, or a bare <task> that "
        "one dataset carries")
    args = parser.parse_args(argv)
    name, task = dataset.split(args.task)
    return seed(REPO_ROOT / "task" / name / task)


if __name__ == "__main__":
    raise SystemExit(main())
