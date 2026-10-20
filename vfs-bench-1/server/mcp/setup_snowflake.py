#!/usr/bin/env python
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from server.mcp.uv_vendor import sync  # noqa: E402

# What to install is `vendor/snowflake-mcp/pyproject.toml`, not this file:
# the remote, the commit, the runtime dependencies and the two cloud clients
# left out of the resolve are all declared there, in uv's own fields, and
# `uv.lock` pins the result. This script only runs the sync and checks that
# the entry point the MCP arm spawns came out of it.
HOME = REPO / "vendor" / "snowflake-mcp"
ENTRY = HOME / ".venv" / "bin" / "mcp_snowflake_server"


def main() -> int:
    return sync(HOME, ENTRY)


if __name__ == "__main__":
    sys.exit(main())
