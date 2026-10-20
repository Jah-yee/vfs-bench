#!/usr/bin/env python
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from server.mcp.npm_lock import installed_version  # noqa: E402

# One install for both tasks: the server takes no configuration and carries
# its own data, so nothing about it is per-task.
HOME = REPO / "vendor" / "howtocook-mcp"
PACKAGE = "howtocook-mcp"
VERSION = "0.2.2"
INSTALLED = HOME / "node_modules" / PACKAGE
CORPUS = INSTALLED / "all_recipes.json"


def write_manifest() -> None:
    """Pin the version in a package.json so the install is reproducible."""
    HOME.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "vfs-bench-howtocook-mcp",
        "private": True,
        "description":
        f"Pinned {PACKAGE}, vendored by {Path(__file__).relative_to(REPO)}",
        "dependencies": {
            PACKAGE: VERSION
        },
    }
    (HOME / "package.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    """Install the pinned server and report what the corpus contains."""
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
    if not CORPUS.is_file():
        print(f"no corpus at {CORPUS}; the package layout has changed",
              file=sys.stderr)
        return 1

    recipes = json.loads(CORPUS.read_text())
    categories = sorted({r.get("category", "") for r in recipes})
    print(f"corpus: {len(recipes)} recipes in {len(categories)} categories "
          f"({CORPUS.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
