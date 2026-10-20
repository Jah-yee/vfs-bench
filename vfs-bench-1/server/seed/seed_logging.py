#!/usr/bin/env python
import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# The dataset seam, not a spelled path: these used to live inside
# `task/toolathlon/` and hardcode it, which is the one thing the seam
# exists to stop.
sys.path.insert(0, str(REPO_ROOT / "agent"))
import dataset  # noqa: E402

sys.path.insert(0, str(REPO_ROOT))

from server.clients import cloud_logging as store  # noqa: E402


def named(task: str, spec: dict) -> str:
    """The bucket one manifest entry means.

    Args:
        task (str): the task name.
        spec (dict): one entry of the manifest's `buckets`, either
            `{"name": ...}` or `{"name_file": <path under the upstream task
            directory>}`.

    Returns:
        str: the bucket id.

    Raises:
        SystemExit: the entry names neither, or the file is missing.
    """
    if "name" in spec:
        return str(spec["name"])
    path = dataset.task_dir(task) / spec.get("name_file", "")
    if not path.is_file():
        sys.exit(f"seed_logging: no bucket name at {path}")
    return path.read_text(encoding="utf-8").strip()


def fill(task: str) -> None:
    """Create the task's log buckets and drop every entry in them.

    Args:
        task (str): the task name.
    """
    # The seeder knows the task, so it composes the per-task endpoint
    # itself; an operator who exported one already means it.
    base = os.environ.get("API_URL", "http://127.0.0.1:9110").rstrip("/")
    os.environ.setdefault(store.ENV, f"{base}/api/{task}/logging")

    manifest = json.loads((dataset.local(task) / "shared" /
                           "logging.json").read_text(encoding="utf-8"))
    project = manifest["project"]
    location = manifest.get("location", "global")
    parent = f"projects/{project}/locations/{location}"

    store.clear_entries()
    for spec in manifest["buckets"]:
        bucket = named(task, spec)
        full = f"{parent}/buckets/{bucket}"
        store.put_bucket(
            full, {
                "retention_days": int(spec.get("retention_days", 30)),
                "description": "",
            })
        print(f"logging: {bucket} ready, no entries")


def main() -> int:
    """Fill one task's log buckets from the command line.

    Returns:
        int: process exit status.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    fill(parser.parse_args().task)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
