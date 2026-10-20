import json
import time
from pathlib import Path

import dataset
from services import REPO_ROOT

# What a dump is named after. Six fields, `_`-separated, in the order they
# are worth reading when the directory is listed: the clock first, so `ls`
# is a run log and `ls | tail` is what just happened; then the five things
# that make a run what it is. Nothing is dropped for being constant today
# -- `toolathlon` is the only dataset in this checkout, and the seam exists
# so that stops being true.
#
# The model's `/` becomes `-` rather than `_`, so `_` stays a separator a
# reader can split on: `openai/gpt-5.6-luna` used to be written
# `openai_gpt-5.6-luna`, which put a field boundary inside a field.
STAMP = "%Y%m%dT%H%M%S"


def run_id(args, task_dir: Path, started: str | None = None) -> str:
    """What one run is called, everywhere it leaves something behind.

    The dump is `dumps/<run_id>.json` and the workspace is
    `state/workspaces/<run_id>/`, so a transcript and the files the run
    produced are paired by name rather than by a reader's memory of what
    was going on that afternoon. Neither is in the task tree.

    No field is dropped for being constant today: `toolathlon` is the only
    dataset in this checkout, and the seam exists so that stops being true.

    Args:
        args: the parsed arguments.
        task_dir (Path): the task directory.
        started (str | None): the run's own clock reading, defaulting to
            now. Passed in by `run_agent`, which reads it before the loop:
            an id minted afterwards would date a run by when it finished.

    Returns:
        str: `<stamp>_<tools>_<model>_<effort>_<dataset>_<task>`.
    """
    return (f"{started or time.strftime(STAMP)}_{args.tools}"
            f"_{getattr(args, 'loop', None) or 'agents'}"
            f"_{args.model.replace('/', '-')}_{args.reasoning_effort}"
            f"_{dataset.NAME}_{task_dir.name}")


def dump_path(args, task_dir: Path, started: str | None = None) -> Path:
    """Where this run's dump goes.

    One directory for every run the checkout has ever done, at the
    repository root and ignored by git. It was `<task_dir>/dumps/`, tracked
    -- which put 46 tasks' worth of previous transcripts, the successful
    arm's included, one `ls ..` from the agent's own working directory on
    the arm whose `python_execute` is a host subprocess. The evidence for a
    published number is the commit it was published in; it does not have to
    sit next to the task to be findable.

    Args:
        args: the parsed arguments; `--dump` overrides all of this.
        task_dir (Path): the task directory.
        started (str | None): the run's own clock reading.

    Returns:
        Path: the file to write, whose parent may not exist yet.
    """
    if args.dump:
        return Path(args.dump)
    return REPO_ROOT / "dumps" / f"{run_id(args, task_dir, started)}.json"


def token_usage(usage) -> dict:
    """The run's cost, per request as well as in total.

    The aggregate alone cannot tell a re-sent tool schema from a cached
    one, and that distinction is the whole claim these runs test -- so the
    per-request breakdown is recorded beside it, showing which request paid
    full price for the prefix and which was served from cache.

    Reasoning tokens are included in output tokens, not added to them.

    Args:
        usage: the run's usage object.

    Returns:
        dict: the `usage` block of the dump.
    """
    return {
        "requests":
        usage.requests,
        "input_tokens":
        usage.input_tokens,
        "output_tokens":
        usage.output_tokens,
        "cached_input_tokens":
        getattr(usage.input_tokens_details, "cached_tokens", None),
        "reasoning_tokens":
        getattr(usage.output_tokens_details, "reasoning_tokens", None),
        "per_request": [{
            "input_tokens":
            entry.input_tokens,
            "output_tokens":
            entry.output_tokens,
            "cached_input_tokens":
            getattr(entry.input_tokens_details, "cached_tokens", None),
            "reasoning_tokens":
            getattr(entry.output_tokens_details, "reasoning_tokens", None),
        } for entry in getattr(usage, "request_usage_entries", [])],
    }


def write_dump(path: Path,
               args,
               task_dir: Path,
               status: str,
               final_output: str,
               usage,
               shell_log: list,
               items: list,
               provenance: dict | None = None,
               started: str | None = None,
               tool_calls: list | None = None) -> None:
    """Write everything about one run that a later reader might want.

    The dump is the measurement: every figure in a task's README is read
    back out of one of these, and a claim about *why* an arm cost what it
    did is settled by reading its transcript.

    Args:
        path (Path): where to write it.
        args: the parsed arguments.
        task_dir (Path): the task directory.
        status (str): "completed", or the exception that ended the run.
        final_output (str): what the model said last.
        usage: the run's usage object.
        shell_log (list): the mirage arms' commands, empty for the MCP arm.
        items (list): the conversation items.
        provenance (dict | None): source fingerprints taken before the run.
        started (str | None): the run's own clock reading, the same one the
            id is minted from. Recorded rather than derived, because
            merging two campaigns' results needs "which run is later" and
            the name is not always the answer: a dump written into a batch
            directory is named after its cell, and a dump renamed by a
            later cleanup carries whatever that cleanup chose. Omitted
            from the dump entirely when there is nothing to record.
        tool_calls (list | None): how long each tool call took, by call id,
            which only the Atlas harness records; omitted likewise.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "provenance":
                provenance or {},
                "model":
                args.model,
                "base_url":
                args.base_url,
                # The variable the key was read from, never the key itself:
                # a grader that asks a judge asks it on the run's gateway and
                # key (`task/mcpatlas/script/grade_task.py`).
                "api_key_env":
                args.api_key_env,
                "tools":
                args.tools,
                "loop":
                getattr(args, "loop", None) or "agents",
                "reasoning_effort":
                args.reasoning_effort,
                "max_turns":
                args.max_turns,
                "max_tokens":
                args.max_tokens,
                "parallel_tool_calls":
                args.parallel_tool_calls,
                "task_dir":
                str(task_dir),
                # Both readings in the harness's own stamp format, from
                # the same clock the id is minted from, so a dump and its
                # id can never disagree about when the run began.
                # `started` is passed in from before the loop and `ended`
                # is taken here, so the pair also says how long the run
                # took. A caller with no reading to give omits the key
                # rather than writing a null: an absent `started` reads
                # as "not recorded", which is what every dump written
                # before this field existed means, where a null would
                # read as "recorded, unknown".
                **({
                    "started": started
                } if started else {}),
                "ended":
                time.strftime(STAMP),
                "status":
                status,
                "final_output":
                final_output,
                "usage":
                token_usage(usage),
                "shell_log":
                shell_log,
                **({
                    "tool_calls": tool_calls
                } if tool_calls is not None else {}),
                # The agents runner hands back its own item objects; Atlas's
                # harness hands back the message dicts it sent, which are
                # already in that form. Both are recorded, so a transcript
                # reads the same whichever loop produced it.
                "items": [
                    item.to_input_item()
                    if hasattr(item, "to_input_item") else item
                    for item in items
                ],
            },
            indent=2,
            default=str))
