#!/usr/bin/env python
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# One install for every notion task: the server is aimed at a workspace by
# BASE_URL and a bearer token at spawn time, so nothing about it is per-task.
SHIM = REPO / "vendor" / "notion-mcp"
PACKAGE = "@notionhq/notion-mcp-server"
VERSION = "1.9.0"
INSTALLED = SHIM / "node_modules" / "@notionhq" / "notion-mcp-server"
PATCH = (REPO / "submodule" / "Toolathlon" / "configs" / "notion-mcp-patches" /
         "notion-openapi.json")


def write_manifest() -> None:
    """Pin the version in a package.json so the install is reproducible."""
    SHIM.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "vfs-bench-notion-mcp",
        "private": True,
        "description": f"Toolathlon's pinned {PACKAGE}, spec overlaid",
        "dependencies": {
            PACKAGE: VERSION
        },
    }
    (SHIM / "package.json").write_text(json.dumps(manifest, indent=2) + "\n")


def install() -> int:
    """npm install the pinned server into the shim directory."""
    print(f"installing {PACKAGE}@{VERSION} into {SHIM}")
    result = subprocess.run(
        ["npm", "install", "--silent", "--no-audit", "--no-fund"],
        cwd=SHIM,
        check=False)
    return result.returncode


def overlay_spec() -> int:
    """Copy Toolathlon's patched spec over the package's own.

    Returns:
        int: 0 on success, 1 if either file is missing.
    """
    if not PATCH.exists():
        print(
            f"error: no patched spec at {PATCH}\n"
            f"run `git submodule update --init Toolathlon` first",
            file=sys.stderr)
        return 1
    target = INSTALLED / "scripts" / "notion-openapi.json"
    if not target.exists():
        print(f"error: {PACKAGE} did not install to {INSTALLED}",
              file=sys.stderr)
        return 1
    shutil.copy2(PATCH, target)
    spec = json.loads(target.read_text())
    count = sum(1 for path in spec["paths"].values() for op in path.values()
                if isinstance(op, dict) and op.get("operationId"))
    print(f"  overlaid Toolathlon's spec ({count} operations)")
    return 0


def main() -> int:
    """Install the pinned server and overlay the patched spec."""
    write_manifest()
    code = install()
    if code != 0:
        print("npm install failed", file=sys.stderr)
        return code
    return overlay_spec()


if __name__ == "__main__":
    sys.exit(main())
