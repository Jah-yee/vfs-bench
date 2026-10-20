#!/usr/bin/env python
"""Install Toolathlon's exact filesystem MCP dependency closure."""
import hashlib
import json
import subprocess
import sys
import tempfile
from functools import cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOME = REPO / "vendor" / "filesystem-mcp"
PACKAGE = "@modelcontextprotocol/server-filesystem"
INSTALLED = HOME / "node_modules" / PACKAGE
ENTRY = INSTALLED / "dist" / "index.js"
INSTALL_LOCK = HOME / "node_modules" / ".package-lock.json"
sys.path.insert(0, str(REPO))


def _source_lock() -> dict:
    """Read the committed Toolathlon lock rather than its working tree."""
    return json.loads(
        subprocess.check_output([
            "git", "-C",
            str(REPO / "submodule/Toolathlon"), "show",
            "HEAD:package-lock.json"
        ]))


VERSION = _source_lock()["packages"]["node_modules/" + PACKAGE]["version"]


def write_manifest(destination: Path = HOME) -> None:
    """Derive the package manifest and complete lock from Toolathlon."""
    from server.mcp.npm_lock import derive
    derive(PACKAGE, destination, "vfs-bench-filesystem-mcp")


def installed_version(installed: Path = INSTALLED) -> str | None:
    """Return the installed package version, if the server is installed."""
    manifest = installed / "package.json"
    if not manifest.is_file():
        return None
    try:
        return str(json.loads(manifest.read_text()).get("version"))
    except json.JSONDecodeError:
        return None


def dependency_fingerprint(lock: Path) -> str | None:
    """Hash every installed package record in one npm v3 lock.

    npm's hidden ``node_modules/.package-lock.json`` is its inventory of the
    installed tree. It omits only the synthetic root project entry, so
    removing that entry from the source lock makes the two inventories
    directly comparable. This catches a changed transitive dependency even
    when the filesystem server's own version and entry point did not move.
    """
    try:
        content = json.loads(lock.read_text())
        packages = content["packages"]
        if not isinstance(packages, dict):
            return None
        inventory = {
            "lockfileVersion": content["lockfileVersion"],
            "packages": {
                path: package
                for path, package in packages.items() if path
            },
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        return None
    encoded = json.dumps(inventory, sort_keys=True,
                         separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def installed_tree_complete(home: Path = HOME) -> bool:
    """Whether every package recorded by npm is present at that version."""
    try:
        content = json.loads(
            (home / "node_modules" / ".package-lock.json").read_text())
        packages = content["packages"]
        if not isinstance(packages, dict):
            return False
        for relative, locked in packages.items():
            if not relative or not isinstance(locked, dict):
                return False
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                return False
            directory = home.joinpath(*path.parts)
            manifest = directory / "package.json"
            if not directory.is_dir() or not manifest.is_file():
                return False
            found = json.loads(manifest.read_text())
            if locked.get("version") != found.get("version"):
                return False
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        return False
    return True


def install_is_current(home: Path = HOME,
                       installed: Path = INSTALLED,
                       entry: Path = ENTRY,
                       version: str = VERSION) -> bool:
    """Whether node_modules was installed from the current derived lock."""
    expected = dependency_fingerprint(home / "package-lock.json")
    actual = dependency_fingerprint(home / "node_modules" /
                                    ".package-lock.json")
    return (installed_version(installed) == version and entry.is_file()
            and expected is not None and actual == expected
            and installed_tree_complete(home))


@cache
def verify_source() -> None:
    """Refuse a committed manifest or lock that differs from Toolathlon."""
    with tempfile.TemporaryDirectory() as directory:
        expected = Path(directory)
        write_manifest(expected)
        for name in ("package.json", "package-lock.json"):
            if (HOME / name).read_bytes() != (expected / name).read_bytes():
                raise ValueError(
                    f"filesystem MCP {name} differs from Toolathlon's lock")


def verify_install() -> None:
    """Refuse a missing server or an install from a different lock."""
    found = installed_version()
    if found != VERSION:
        raise ValueError(f"expected {PACKAGE}@{VERSION}, found {found}")
    if not ENTRY.is_file():
        raise FileNotFoundError(f"no server at {ENTRY}; run `uv run python "
                                "server/mcp/setup_filesystem.py`")
    expected = dependency_fingerprint(HOME / "package-lock.json")
    installed = dependency_fingerprint(INSTALL_LOCK)
    if expected is None or installed != expected:
        raise ValueError("filesystem MCP node_modules does not match the "
                         "complete derived package-lock; run `uv run python "
                         "server/mcp/setup_filesystem.py`")
    if not installed_tree_complete():
        raise ValueError("filesystem MCP node_modules is incomplete; run `uv "
                         "run python server/mcp/setup_filesystem.py`")


def main() -> int:
    """Install the exact dependency tree and verify its entry point."""
    write_manifest()
    if install_is_current():
        print(f"{PACKAGE}@{VERSION} already vendored at {HOME}")
    else:
        print(f"installing {PACKAGE}@{VERSION} into {HOME} ...")
        result = subprocess.run([
            "npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund",
            "--silent"
        ],
                                cwd=HOME,
                                check=False)
        if result.returncode != 0:
            print(f"npm install failed ({result.returncode})", file=sys.stderr)
            return 1
    verify_source.cache_clear()
    verify_source()
    verify_install()
    print(f"server: {ENTRY.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
