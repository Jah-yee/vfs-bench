#!/usr/bin/env python
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from server.mcp.npm_lock import installed_version  # noqa: E402

# The package upstream's huggingface.yaml runs, and the directory is named
# after it rather than after the server: mcp-remote is a stdio-to-HTTP
# bridge, not a Hugging Face server, and the tools it carries are whatever
# the endpoint behind it advertises.
HOME = REPO / "vendor" / "mcp-remote"
PACKAGE = "mcp-remote"
# Upstream runs `npx mcp-remote` with no version, so its own arm resolves
# whatever npm publishes that day. Pinning is this repo's divergence, and it
# is the same one every vendored server here makes: an unpinned bridge could
# change how a tool document is relayed between two draws of one benchmark.
VERSION = "0.8.2"
INSTALLED = HOME / "node_modules" / PACKAGE
ENTRY = INSTALLED / "dist" / "proxy.js"


def write_manifest() -> None:
    """Pin the version in a package.json so the install is reproducible."""
    HOME.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "vfs-bench-mcp-remote",
        "private": True,
        "description":
        f"Pinned {PACKAGE}, vendored by {Path(__file__).relative_to(REPO)}",
        "dependencies": {
            PACKAGE: VERSION
        },
    }
    (HOME / "package.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    """Install the pinned bridge and report where its entry point is."""
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
        print(f"no entry point at {ENTRY}; the package layout has changed",
              file=sys.stderr)
        return 1
    print(f"bridge: {ENTRY.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
