import importlib.util
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from services import REPO_ROOT, agent_workspace, seed_record

sys.path.insert(0, str(REPO_ROOT / "task"))

import dataset  # noqa: E402


def entrypoint(path):
    """Import a project entry point rather than starting a sibling
    interpreter."""
    spec = importlib.util.spec_from_file_location(
        "benchmark_" + dataset.NAME.replace("-", "_") + "_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def project_environment():
    """Preserve the previous subprocess's cwd and dataset selection."""
    previous = os.environ.get("BENCH_DATASET")
    cwd = Path.cwd()
    os.environ["BENCH_DATASET"] = dataset.NAME
    os.chdir(REPO_ROOT)
    try:
        yield
    finally:
        os.chdir(cwd)
        if previous is None:
            os.environ.pop("BENCH_DATASET", None)
        else:
            os.environ["BENCH_DATASET"] = previous


def seed(task_dir: Path) -> int:
    """Rebuild the task's fixtures, wiping what the previous arm left.

    Both arms run against the same live services one after the other, so a
    fixture left as the previous arm finished with it is the previous arm's
    answer sitting in front of this one. The workspace is a fixture too and
    is emptied with the rest -- inside the dataset's own seeder, which is
    where the four builders that write into it run, and which is also what
    a stack
    set up by hand calls. Emptying it here as well would be a second copy
    of that decision, and a second place to resolve the path from.

    Args:
        task_dir (Path): the task directory.

    Returns:
        int: `server/seed/seed_task.py`'s exit status.
    """
    with project_environment():
        return entrypoint(dataset.seeder()).main([task_dir.name])


def seeded_at(task_dir: Path) -> str:
    """When this run's fixtures were seeded.

    Args:
        task_dir (Path): the task directory.

    Returns:
        str: the seed's timestamp, or now if nothing has been seeded --
            which a run cannot reach, since it seeds first, but a grader
            invoked by hand on a cold stack can.
    """
    record = seed_record(task_dir)
    if record.is_file():
        found = json.loads(record.read_text()).get("seeded_at")
        if found:
            return found
    return time.strftime("%Y-%m-%d %H:%M:%S")


def run_status(dump_file: Path | None) -> str:
    """What the run itself recorded as its outcome.

    `completed` where there is no dump to ask, which is how `grade_task.py`
    is invoked by hand and how the fidelity tests call in.

    Args:
        dump_file (Path | None): the run's dump, or None.

    Returns:
        str: the run's status.
    """
    if dump_file is None or not dump_file.is_file():
        return "completed"
    return json.loads(dump_file.read_text()).get("status") or "completed"


def ungraded(dump_file: Path | None) -> str | None:
    """The run status that stops this run being graded, if it is one.

    Refusing to grade an unfinished run is upstream Toolathlon's rule, not
    a rule of this repo, so it is asked of the dataset rather than applied
    to all four. Atlas is the case that makes the difference: its runner
    takes the last assistant message with content as the response and
    scores it against the row's claims, with no notion of a run status at
    all -- `run_eval.py:186` keeps the row even for a timeout or an HTTP
    error. A turn-limited Atlas run that still answered has an answer to
    grade, and Toolathlon's `pass: None` would throw it away.

    Args:
        dump_file (Path | None): the run's dump; None when the caller has
            no run behind it, which is how `grade_task.py` is invoked by
            hand and how the fidelity tests call in.

    Returns:
        str | None: the status, or None when the evaluator should see the
            run -- because it finished, or because the dataset grades an
            unfinished one.
    """
    if getattr(dataset, "GRADES_UNFINISHED", True):
        return None
    status = run_status(dump_file)
    return None if status == "completed" else status


def record(dump_file: Path | None,
           code: int | None,
           status: str,
           sha: str | None = None) -> None:
    """Write what grading decided back into the run's dump.

    Args:
        dump_file (Path | None): the run's dump, or None.
        code (int | None): the evaluator's exit status, or None where the
            run was not graded at all.
        status (str): the run status grading saw.
        sha (str | None): the evaluator tree digest, where one was taken.
    """
    if dump_file is None or not dump_file.is_file():
        return
    written = json.loads(dump_file.read_text())
    written["evaluation"] = {
        "evaluator_sha": sha,
        "exit_code": code,
        "run_status": status
    }
    dump_file.write_text(json.dumps(written, indent=2) + "\n")


# Every way this path diverges from upstream's own grading driver,
# `utils/evaluation/evaluator.py` `TaskEvaluator.evaluate_one`, which is the
# code that decides a Toolathlon grade upstream. The evaluator itself is not
# restated -- `dataset.evaluator_argv` runs upstream's own module in
# upstream's own virtualenv -- so what is listed here is the call around it.
#
#   res_log_file   upstream hands the run's trajectory log. The evaluators in
#                  this pool read it but none scores it, so `grade_task.py`
#                  passes a stub with the shape they destructure. A dataset
#                  whose evaluator scores the transcript gets the real dump
#                  through `--dump` instead (`dataset.GRADES_TRANSCRIPT`).
#
#   groundtruth_workspace
#                  upstream always passes it, and renders the string "None"
#                  for the 35 tasks that ship no ground truth, because it
#                  interpolates the field into the command line either way.
#                  This omits the flag there instead, so an evaluator that
#                  reads the path gets no path rather than a directory
#                  named "None".
#
#   status gate    upstream refuses to grade a run that did not end in
#                  `TaskStatus.SUCCESS` and reports `pass: None` -- neither a
#                  pass nor a failure of the answer. `grade` does the same
#                  below: an arm that timed out or raised is not measured
#                  against the fixture it never finished changing. This is
#                  Toolathlon's rule and is declared per dataset
#                  (`dataset.GRADES_UNFINISHED`), because a dataset whose own
#                  runner grades whatever the agent last said would lose that
#                  answer to a rule its upstream does not have.
#
#   result shape   upstream answers `{"pass": bool | None}`; this answers the
#                  evaluator's exit status, which `run_agent.py` combines with
#                  the run status the same way. `None` is the gate above.


def grade(task_dir: Path, dump_file: Path | None = None) -> int:
    """Run the task's upstream evaluator against what the arm left behind.

    The batch script used to run `grade_task.py` after each arm; a run
    grades itself now, so one command is the whole per-arm procedure. The
    evaluator tree digest is printed first, the way the batch recorded it,
    so parity between arms stays visible in every log.

    The launch time comes from the seed's own record rather than from the
    caller. It is when this task's fixtures came into existence, which is
    what upstream's evaluator means by it -- and taking it from anywhere
    else is how it once ended up being the *previous* task's.

    Args:
        task_dir (Path): the task directory.

    Returns:
        int: the evaluator's exit status; 0 where there is no evaluator,
            and 1 where the run did not finish, which upstream reports as
            `pass: None` rather than grading.
    """
    evaluator = dataset.evaluator(task_dir.name)
    if not evaluator.is_file():
        print(f"no evaluator at {evaluator}; nothing to grade")
        return 0
    status = ungraded(dump_file)
    if status is not None:
        print(f"run status {status}; not graded")
        record(dump_file, None, status)
        return 1
    grader = dataset.local(task_dir.name).parent / "script" / "grade_task.py"
    launch_time = seeded_at(task_dir)
    with project_environment():
        module = entrypoint(grader)
        sha = (getattr(module, "evaluator_sha", None)
               or module.digest)(task_dir.name)
    print(f"evaluator_sha={sha}")
    # Resolved, not rebuilt. `build_workspace_dir` is the SETUP path: it
    # copies `initial_workspace/` in and skips what is already there. Called
    # here, after the arm has run, that copy restores every file the agent
    # deleted or renamed away -- and then the evaluator reads the directory.
    #
    # `university-course-selection` is where that decides a grade. The ask
    # says "delete any other unnecessary Excel files (including the
    # reference format)", and `check_local.py` counts `.xlsx` in the
    # workspace and fails on `File count mismatch`. An agent that deleted
    # `reference_format.xlsx` had it put back before it was counted.
    #
    # It also made the "possible leak into the run" warning fire on every
    # graded run, where the leftovers it names are the agent's own output.
    # A warning that is always wrong is a warning nobody reads.
    argv = [
        task_dir.name, "--agent-workspace",
        str(agent_workspace(task_dir)), "--launch-time", launch_time
    ]
    # A dataset that grades what the arm *said* rather than what it left
    # behind needs the transcript. Toolathlon reads the fixture back out of
    # the fakes and never looks at the dump; Atlas ships no evaluator at all
    # and scores the final message against the row's claims, so for it the
    # dump is the whole input and the workspace is not consulted.
    if getattr(dataset, "GRADES_TRANSCRIPT", False) and dump_file is not None:
        argv += ["--dump", str(dump_file)]
    with project_environment():
        code = module.main(argv)
    print(f"eval_exit={code}")
    record(dump_file, code, run_status(dump_file), sha)
    return code
