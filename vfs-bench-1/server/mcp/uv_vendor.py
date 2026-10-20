"""Sync a vendored Python MCP server from its own uv project."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def sync(home: Path, entry: Path) -> int:
    """Sync the vendored server's project, and check its entry point.

    What to install is the vendored `pyproject.toml` and its `uv.lock`, never
    this file: the remote, the commit and the runtime dependencies are all
    declared there, in uv's own fields. This only runs the sync and checks
    that the entry point the MCP arm spawns came out of it.

    Args:
        home (Path): the vendored project's directory.
        entry (Path): the executable the MCP arm spawns.

    Returns:
        int: process exit status.
    """
    print(f"syncing {home.relative_to(REPO)} ...")
    done = subprocess.run(["uv", "sync", "--project", str(home)], check=False)
    if done.returncode != 0:
        print(f"uv sync failed ({done.returncode})", file=sys.stderr)
        return done.returncode

    if not entry.is_file():
        print(f"no server at {entry}; the package layout has changed",
              file=sys.stderr)
        return 1
    print(f"server: {entry.relative_to(REPO)}")
    return 0
