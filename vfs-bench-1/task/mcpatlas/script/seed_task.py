#!/usr/bin/env python
import argparse
import json
import sys
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


def main(argv=None) -> int:
    """Put one task's fixture back to its starting state.

    Which here means copying the pinned image's `/data` out, under
    `state/`. Atlas has one such tree for all 500 of its tasks, so this
    builds the same directory for every task and `arms.build_workspace_dir`
    copies it into a workspace named after the run, which the mirage arm
    mounts; the MCP arm's servers read the image's own, in a container of
    the run's. Two arms of one draw therefore never share a directory, and
    there is no previous arm's answer to wipe.

    Keying the directory by the image is what keeps a new pin from editing
    a tree a previous run was measured against.

    Returns:
        int: 0 when the tree is where the seam says it is.
    """
    parser = argparse.ArgumentParser(
        description="Build one task's fixture and describe what both arms "
        "will start from.")
    parser.add_argument("task")
    parser.add_argument("--check",
                        action="store_true",
                        help="report whether the tree is already built, "
                        "without building it")
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
    if not spec.get("atlas_task"):
        print(
            f"seed_task: {manifest} names no `atlas_task`, so there is no "
            f"upstream row behind it",
            file=sys.stderr)
        return 1

    tree = dataset.environment()
    if args.check:
        if not tree.is_dir():
            print(f"seed_task: {tree} is not built", file=sys.stderr)
            return 1
        names = dataset.tree_files(tree)
    else:
        names = dataset.build_environment()

    print(f"fixture: {dataset.IMAGE}:/data, image {dataset.image_id()[:12]}")
    print(f"  into={tree} files={len(names)}")
    for name in names:
        print(f"    {name}")
    for row in tree.joinpath(*dataset.CLONES).read_text().splitlines():
        if row.strip():
            url, sha, where = row.split(",", 2)
            print(f"  clone {where}: {url} at {sha[:12]}")
    print(f"  venv /data/{dataset.VENV}")

    declaration = dataset.declaration(args.task)
    print(f"ready: {args.task} (atlas task {declaration['task']}, "
          f"{len(declaration['enabled_tools'])} tools)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
