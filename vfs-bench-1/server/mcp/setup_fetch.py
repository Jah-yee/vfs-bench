#!/usr/bin/env python
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from server.mcp.npm_lock import installed_version  # noqa: E402

HOME = REPO / "vendor" / "fetch-mcp"
PACKAGE = "@tokenizin/mcp-npx-fetch"
VERSION = "1.0.0"
INSTALLED = HOME / "node_modules" / PACKAGE
ENTRY = INSTALLED / "dist" / "index.js"


def write_manifest() -> None:
    """Pin the version in a package.json so the install is reproducible."""
    HOME.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "vfs-bench-fetch-mcp",
        "private": True,
        "description":
        f"Pinned {PACKAGE}, vendored by {Path(__file__).relative_to(REPO)}",
        "dependencies": {
            PACKAGE: VERSION
        },
    }
    (HOME / "package.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    """Install the pinned server and confirm its entry point is there."""
    write_manifest()
    if installed_version(INSTALLED) == VERSION:
        print(f"{PACKAGE}@{VERSION} already vendored at {HOME}")
    else:
        print(f"installing {PACKAGE}@{VERSION} into {HOME} ...")
        result = subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", "--silent"],
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
