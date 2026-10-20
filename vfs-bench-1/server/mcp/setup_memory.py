#!/usr/bin/env python
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOME = REPO / "vendor" / "memory-mcp"
PACKAGE = "@modelcontextprotocol/server-memory"
sys.path.insert(0, str(REPO))
from server.mcp.npm_lock import installed_version  # noqa: E402
from server.seed.kubernetes import original  # noqa: E402

VERSION = json.loads(
    original('package-lock.json'))['packages']['node_modules/' +
                                               PACKAGE]['version']

INSTALLED = HOME / "node_modules" / PACKAGE
ENTRY = INSTALLED / "dist" / "index.js"


def write_manifest() -> None:
    """Pin the version in a package.json so the install is reproducible."""
    from server.mcp.npm_lock import derive
    derive(PACKAGE, HOME, 'vfs-bench-memory-mcp')


def main() -> int:
    """Install the pinned server and confirm its entry point is there."""
    write_manifest()
    if installed_version(INSTALLED) == VERSION:
        print(f"{PACKAGE}@{VERSION} already vendored at {HOME}")
    else:
        print(f"installing {PACKAGE}@{VERSION} into {HOME} ...")
        result = subprocess.run(
            [
                "npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund",
                "--silent"
            ],
            cwd=HOME,
            check=False,
        )
        if result.returncode != 0:
            print(f"npm install failed ({result.returncode})", file=sys.stderr)
            return 1

    found = installed_version(INSTALLED)
    if found != VERSION:
        print(f"expected {PACKAGE}@{VERSION}, found {found}", file=sys.stderr)
        return 1
    if not ENTRY.is_file():
        print(f"no server at {ENTRY}; the package layout has changed",
              file=sys.stderr)
        return 1
    print(f"server: {ENTRY.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
