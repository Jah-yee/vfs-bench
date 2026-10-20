import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEST = REPO_ROOT / "vendor" / "pyodide-packages"

# READ from the pyodide the TypeScript arm loads, never written down here. A
# wheel built for another ABI will not import, and the failure surfaces as a
# bare ModuleNotFoundError well after the point that caused it -- so a
# constant that drifts from the installed version is the exact defect this
# has to avoid. It drifted once already: the pin moved pyodide 0.29.3 ->
# 314.0.5, whose wheels are cp314/pyemscripten_2026 where the vendored ones
# were cp313/pyodide_2025, and nothing said so.

# What this dataset's tasks import and pyodide does not carry by default.
# `pymupdf` is a C extension, so it cannot come off `/opt/wheels` with the
# pure-Python ones and loads through pyodide's own resolver instead; two
# tasks name it -- notion-hr and travel-expense-reimbursement.
# pandas and pyarrow are in pyodide's own distribution but not on disk: the
# npm package carries no wheels and fetches them from a CDN, which a run
# behind NO_NETWORK cannot do. `verl-dataset` is graded on a parquet file,
# so the mirage arm needs both here or it cannot answer the task at all.
# The list belongs to the dataset, which is why this sits beside it; the
# calendar tasks also need tzdata for named-zone conversions with zoneinfo.
# Pillow and lxml support the task's image and document imports.
WANTED = ("pymupdf", "pandas", "pyarrow", "tzdata", "pillow", "lxml")


def installed() -> Path:
    """Locate the pyodide the TypeScript arm actually loads.

    Returns:
        Path: the installed package directory.

    Raises:
        SystemExit: if the TypeScript dependencies are not installed.
    """
    root = REPO_ROOT / "submodule" / "mirage" / "typescript" / "node_modules"
    found = sorted(root.glob(".pnpm/pyodide@*/node_modules/pyodide"))
    if not found:
        raise SystemExit("no pyodide in node_modules: run `pnpm install` in "
                         "submodule/mirage/typescript first")
    return found[0]


def version() -> str:
    """The installed pyodide's version, which names the CDN to fetch from.

    Returns:
        str: the version, as its own package.json states it.
    """
    return json.loads((installed() / "package.json").read_text())["version"]


def lock_path() -> Path:
    """The installed pyodide's lock file.

    Returns:
        Path: the lock file.
    """
    return installed() / "pyodide-lock.json"


def wheels_for(names: tuple[str, ...]) -> list[tuple[str, str]]:
    """Resolve package names to their wheel filenames, dependencies included.

    Args:
        names (tuple[str, ...]): top-level package names.

    Returns:
        list[tuple[str, str]]: (package, wheel filename) pairs.
    """
    packages = json.loads(lock_path().read_text())["packages"]
    seen: dict[str, str] = {}
    queue = list(names)
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        entry = packages.get(name)
        if entry is None:
            raise SystemExit(f"{name} is not in pyodide {version()}")
        seen[name] = entry["file_name"]
        queue.extend(entry.get("depends", []))
    return sorted(seen.items())


def main() -> int:
    """Download the wheels, or report what is missing.

    Returns:
        int: process exit status.
    """
    ap = argparse.ArgumentParser(
        description='Vendor the pyodide wheels the mirage arm '
        'loads at runtime.')
    ap.add_argument("--check",
                    action="store_true",
                    help="report presence without downloading")
    args = ap.parse_args()

    DEST.mkdir(parents=True, exist_ok=True)
    packages = json.loads(lock_path().read_text())["packages"]
    missing = 0
    for name, wheel in wheels_for(WANTED):
        target = DEST / wheel
        expected = packages[name]["sha256"]
        if target.is_file() and hashlib.sha256(
                target.read_bytes()).hexdigest() == expected:
            print(f"have {name:16} {wheel}")
            continue
        if args.check:
            print(f"MISSING {name:16} {wheel}")
            missing += 1
            continue
        print(f"fetch {name:16} {wheel}")
        cdn = f"https://cdn.jsdelivr.net/pyodide/v{version()}/full/"
        with urllib.request.urlopen(cdn + wheel) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise SystemExit(f"hash mismatch for {wheel}")
        target.write_bytes(data)
        print(f"      {target.stat().st_size / 1e6:.1f} MB")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
