#!/usr/bin/env python
import argparse
import json
import os
import sys
from pathlib import Path

from google.cloud import storage

REPO_ROOT = Path(__file__).resolve().parents[2]
# The dataset seam, not a spelled path: these used to live inside
# `task/toolathlon/` and hardcode it, which is the one thing the seam
# exists to stop.
sys.path.insert(0, str(REPO_ROOT / "agent"))
import dataset  # noqa: E402


def named(task: str, spec: dict) -> str:
    """The bucket one manifest entry means.

    Args:
        task (str): the task name.
        spec (dict): one entry of the manifest's `buckets`, either
            `{"name": ...}` or `{"name_file": <path under the upstream task
            directory>}`.

    Returns:
        str: the bucket name.

    Raises:
        SystemExit: the entry names neither, or the file is missing.
    """
    if "name" in spec:
        return str(spec["name"])
    path = dataset.task_dir(task) / spec.get("name_file", "")
    if not path.is_file():
        sys.exit(f"seed_gcs: no bucket name at {path}")
    return path.read_text(encoding="utf-8").strip()


def recreate(client: storage.Client, name: str) -> None:
    """Drop the bucket and its contents, then make it again, empty.

    Args:
        client (storage.Client): the client, pointed at the fake.
        name (str): the bucket.
    """
    bucket = client.bucket(name)
    if bucket.exists():
        # force= deletes the objects with it; the fake has no lifecycle
        # rules and no versioning, so one pass is enough.
        bucket.delete(force=True)
    client.create_bucket(name)


def drop_prefixed(client: storage.Client, prefix: str) -> list[str]:
    """Delete every bucket whose name starts with `prefix`, making none.

    The other half of this file recreates a bucket the task reads from. This
    half is for the opposite fixture: a bucket the task's *answer* is that
    the agent created it. `ab-testing` is graded by whether anything
    matching `promo-assets-for-b` exists, so the seed has to leave nothing
    matching -- and cannot leave an empty one either, because an empty one
    is already the passing answer.

    Prefix and not a name, because the agent picks the suffix. Upstream's
    own preprocess deletes by the same prefix
    (`preprocess/ggcloud_clean_bucket.py`), which is what this follows.

    Both arms run one after the other against the one emulator, so without
    this the second arm inherits the first arm's bucket and is graded as
    having created it.

    Args:
        client (storage.Client): the client, pointed at the fake.
        prefix (str): the name prefix.

    Returns:
        list[str]: the buckets deleted.
    """
    gone = []
    for bucket in list(client.list_buckets()):
        if not bucket.name.startswith(prefix):
            continue
        client.bucket(bucket.name).delete(force=True)
        gone.append(bucket.name)
    return gone


def recreate_buckets(task: str) -> None:
    """Recreate every bucket the task's manifest names, empty.

    An entry is either a bucket to have (`name` or `name_file`) or a prefix
    to have none of (`prefix`); see `drop_prefixed` for why the second kind
    exists.

    Args:
        task (str): the task name.

    Raises:
        SystemExit: the emulator is not pointed at, which would mean
            deleting buckets in the real Cloud Storage.
    """
    if not os.environ.get("STORAGE_EMULATOR_HOST"):
        raise SystemExit("seed_gcs: STORAGE_EMULATOR_HOST is unset; this "
                         "would reach the real Cloud Storage")

    manifest = json.loads((dataset.local(task) / "shared" /
                           "storage.json").read_text(encoding="utf-8"))
    client = storage.Client(project=manifest["project"])
    for spec in manifest["buckets"]:
        if "prefix" in spec:
            gone = drop_prefixed(client, spec["prefix"])
            print(f"gcs: nothing matching {spec['prefix']}, "
                  f"dropped {len(gone)}")
            continue
        name = named(task, spec)
        recreate(client, name)
        print(f"gcs: {name} recreated, empty")


def main() -> int:
    """Recreate one task's buckets from the command line.

    Returns:
        int: process exit status.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    recreate_buckets(parser.parse_args().task)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
