#!/usr/bin/env python
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "task"))
sys.path.insert(0, str(REPO_ROOT / "agent"))

import dataset  # noqa: E402

# This script lives inside the dataset it serves, so it names it from its own
# path rather than inheriting whatever the caller happened to have loaded.
# `grading.child_env` sets BENCH_DATASET for the children *it* spawns, but dvc
# and a bare shell do not, and the default would quietly be the other dataset
# -- which is how this first resolved `task/toolathlon/fantasy-sports-average`.
dataset.use(Path(__file__).resolve().parents[1].name)

# MCP-Atlas publishes its 500 tasks as one parquet on the Hub rather than as
# files in the repository, so this is the pin -- the same role
# `submodule/mcp-atlas` plays for the fixture tree. A revision, never `main`:
# the row carries the ask the model is given and the claims it is graded on,
# and a floating source would let both move without anything noticing.
DATASET = "ScaleAI/MCP-Atlas"
REVISION = "8c563b55d7c967755f474299848049834d624617"
PARQUET = "MCP-Atlas.parquet"
URL = (f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/"
       f"{PARQUET}")

# Upstream's own column names, kept rather than renamed so that a reader can
# put this file and the Hub's viewer side by side.
COLUMNS = ("TASK", "ENABLED_TOOLS", "PROMPT", "GTFA_CLAIMS")


def rows() -> list[dict]:
    """Every task in the dataset, at the pinned revision.

    Returns:
        list[dict]: one dict per row, upstream's column names.
    """
    import pandas

    cache = REPO_ROOT / "state" / "mcpatlas" / f"{REVISION[:12]}-{PARQUET}"
    if not cache.is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        print(f"fetching {URL}")
        with urllib.request.urlopen(URL, timeout=180) as response:
            cache.write_bytes(response.read())
    return pandas.read_parquet(cache,
                               columns=list(COLUMNS)).to_dict(orient="records")


def tool_names(value) -> list[str]:
    """Normalise one row's ENABLED_TOOLS to a list of names.

    Upstream's own `_tool_names` (`run_eval.py`): entries are either plain
    tool-name strings or tool-definition objects carrying one.

    Args:
        value: the column's value, a JSON-encoded list.

    Returns:
        list[str]: model-facing tool names, in upstream's order.
    """
    found = []
    for item in json.loads(value):
        if isinstance(item, str):
            found.append(item)
        elif isinstance(item, dict) and item.get("name"):
            found.append(item["name"])
    return found


def claims(value: str) -> list[str]:
    """One row's GTFA_CLAIMS, which upstream stores as a Python literal.

    Args:
        value (str): the column's value.

    Returns:
        list[str]: the claims, verbatim.
    """
    import ast

    return list(ast.literal_eval(value))


def main() -> int:
    """Rebuild one task's ask and declaration from the pinned dataset row.

    Writes two files and no more. `shared/task.md` is the ask, handed to both
    arms byte for byte; `shared/atlas.json` is upstream's declaration -- the
    task id, the tools, the claims.

    Returns:
        int: 0 when both files match the pinned row.
    """
    if len(sys.argv) != 2:
        raise SystemExit("usage: derive_task.py <task>")
    task = sys.argv[1]

    spec = json.loads(dataset.manifest(task).read_text())
    wanted = spec.get("atlas_task")
    if not wanted:
        raise SystemExit(f"derive_task: {dataset.manifest(task)} names no "
                         f"`atlas_task`, so there is no row to derive from")

    found = [row for row in rows() if str(row["TASK"]).strip() == wanted]
    if not found:
        raise SystemExit(f"derive_task: {DATASET}@{REVISION[:12]} has no "
                         f"task {wanted}")
    row = found[0]

    local = dataset.local(task)
    # Verbatim: no strip, no trailing newline. This file *is* what the model
    # is sent -- `run_agent.py` reads it and passes it as the user message,
    # and upstream's `run_eval.py` puts the column straight into
    # `messages[0].content` -- so a byte added here is a byte the model gets
    # that Atlas never sent it, which is the one thing a divergence may not
    # do. Not hypothetical at this revision: 40 of the 500 prompts end in
    # whitespace and 2 carry newlines, one inside a ```js fence.
    # `task/*/*/shared/task.md` is excluded from the whitespace hooks so
    # end-of-file-fixer cannot put the newline back.
    (local / "shared" / "task.md").write_bytes(str(row["PROMPT"]).encode())
    (local / "shared" / "atlas.json").write_text(
        json.dumps(
            {
                "dataset": f"{DATASET}@{REVISION}",
                "task": str(row["TASK"]).strip(),
                "enabled_tools": tool_names(row["ENABLED_TOOLS"]),
                "claims": claims(row["GTFA_CLAIMS"]),
            },
            indent=2) + "\n")
    print(f"{task}: row {wanted} from {DATASET}@{REVISION[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
