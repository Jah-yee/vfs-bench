"""Build arrange-workspace's upstream-supported Python packages for Pyodide."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
UPSTREAM = REPO_ROOT / "submodule" / "Toolathlon"
DEST = REPO_ROOT / "vendor" / "toolathlon-python"

# Task packages available in upstream's local-python-execute. Its image
# also installs opencv-python, which cannot be imported there (no
# libGL.so.1), and pytesseract with no tesseract binary; so cv2 is left out
# and pytesseract ships without an engine.
WANTED = (
    "openpyxl",
    "xlsxwriter",
    "pypdf2",
    "pymupdf",
    "pandas",
    "numpy",
    "pyarrow",
    "pillow",
    "lxml",
    "python-docx",
    "python-pptx",
    "pytesseract",
    "olefile",
    # Calendar tasks already load this for named-zone conversions.
    "tzdata",
)
CDN = "https://cdn.jsdelivr.net/pyodide/v{version}/full/"


def normalize(name: str) -> str:
    """Normalize a distribution name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def pyodide_dir() -> Path:
    """Locate the installed TypeScript Pyodide package."""
    root = REPO_ROOT / "submodule" / "mirage" / "typescript" / "node_modules"
    found = sorted(root.glob(".pnpm/pyodide@*/node_modules/pyodide"))
    if not found:
        raise SystemExit("no pyodide in node_modules: run `pnpm install` in "
                         "submodule/mirage/typescript first")
    return found[0]


def installed_upstream() -> dict[str, str]:
    """Read package versions from the upstream Python environment."""
    if not (UPSTREAM / ".venv").is_dir():
        raise SystemExit("upstream's environment is missing: run "
                         f"`uv sync --locked --project {UPSTREAM}` first")
    code = ("import importlib.metadata as m, json;"
            "print(json.dumps({d.metadata['Name']: d.version "
            "for d in m.distributions()}))")
    out = subprocess.run([
        "uv", "run", "--no-sync", "--project",
        str(UPSTREAM), "python", "-c", code
    ],
                         check=True,
                         capture_output=True,
                         text=True).stdout
    return {normalize(k): v for k, v in json.loads(out).items()}


def upstream_lock() -> dict[str, dict]:
    """Index upstream lock entries by normalized package name."""
    lock = tomllib.loads((UPSTREAM / "uv.lock").read_text())
    return {normalize(p["name"]): p for p in lock["package"]}


def pure_wheel(entry: dict) -> tuple[str, str, str] | None:
    """Return a universal wheel as (filename, URL, SHA-256), if available."""
    for wheel in entry.get("wheels", []):
        name = wheel["url"].rsplit("/", 1)[-1]
        if name.endswith("-none-any.whl"):
            return name, wheel["url"], wheel["hash"].removeprefix("sha256:")
    return None


def fetch(url: str, sha256: str) -> bytes:
    """Download a file and verify its SHA-256."""
    with urllib.request.urlopen(url) as reply:
        body = reply.read()
    if hashlib.sha256(body).hexdigest() != sha256:
        raise SystemExit(f"hash mismatch for {url}")
    return body


def imports_of(wheel: Path) -> list[str]:
    """Find import names from shipped wheel files, not top_level.txt."""
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    found = set()
    for name in names:
        head = name.split("/", 1)[0]
        if head.endswith((".dist-info", ".data")) or head.startswith("_"):
            continue
        if "/" in name and f"{head}/__init__.py" in names:
            found.add(head)
        elif "/" not in name and name.endswith(".py"):
            found.add(name[:-3])
        elif name.endswith("/__init__.py"):
            # Register the first concrete package inside a namespace.
            parts = name.split("/")[:-1]
            for length in range(1, len(parts) + 1):
                prefix = parts[:length]
                if "/".join(prefix) + "/__init__.py" in names:
                    found.add(".".join(prefix))
                    break
    return sorted(n for n in found
                  if all(part.isidentifier() for part in n.split(".")))


def main(argv: list[str] | None = None) -> int:
    """Build or verify the task package bundle."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check",
                    action="store_true",
                    help="verify the bundle without downloading")
    args = ap.parse_args(argv)
    installed = pyodide_dir()
    stock = json.loads((installed / "pyodide-lock.json").read_text())
    version = json.loads((installed / "package.json").read_text())["version"]
    by_pyodide = {normalize(k): v for k, v in stock["packages"].items()}
    locked = upstream_lock()
    upstream = installed_upstream()
    packages = {}
    sources = {}
    jobs = {}

    def take(name):
        name = normalize(name)
        if name in packages:
            return
        if name in by_pyodide:
            entry = dict(by_pyodide[name])
            entry["name"] = name
            entry["depends"] = [normalize(d) for d in entry.get("depends", [])]
            url = CDN.format(version=version) + entry["file_name"]
            origin = "pyodide"
        else:
            source = locked.get(name)
            wheel = pure_wheel(source) if source else None
            if not wheel:
                raise SystemExit(
                    f"no compatible wheel for required package {name}")
            filename, url, sha256 = wheel
            entry = {
                "name":
                name,
                "version":
                source["version"],
                "file_name":
                filename,
                "sha256":
                sha256,
                "install_dir":
                "site",
                "package_type":
                "package",
                "imports": [],
                "depends":
                [normalize(d["name"]) for d in source.get("dependencies", [])],
                "unvendored_tests":
                False,
            }
            origin = "upstream"
        packages[name] = entry
        jobs[name] = url
        sources[name] = {
            "source": origin,
            "upstream": upstream.get(name),
            "bundled": entry["version"],
        }
        for dependency in entry["depends"]:
            take(dependency)

    for name in WANTED:
        if name not in upstream:
            raise SystemExit(
                f"{name} is not installed in upstream's Python tool")
        if name not in locked or upstream[name] != locked[name]["version"]:
            raise SystemExit(f"upstream environment differs from uv.lock: "
                             f"{name}=={upstream[name]}; sync upstream first")
        take(name)
    for name in packages:
        if name in upstream and (name not in locked
                                 or upstream[name] != locked[name]["version"]):
            raise SystemExit(f"upstream environment differs from uv.lock: "
                             f"{name}=={upstream[name]}; sync upstream first")

    DEST.mkdir(parents=True, exist_ok=True)
    missing = 0
    for name, entry in packages.items():
        target = DEST / entry["file_name"]
        if (target.is_file() and hashlib.sha256(
                target.read_bytes()).hexdigest() == entry["sha256"]):
            continue
        if args.check:
            print(f"MISSING or INVALID {target.name}")
            missing += 1
        else:
            print(f"fetch {target.name}")
            target.write_bytes(fetch(jobs[name], entry["sha256"]))
    if missing:
        return 1
    for name, entry in packages.items():
        if sources[name]["source"] == "upstream":
            entry["imports"] = imports_of(DEST / entry["file_name"])
    lock = {"info": stock["info"], "packages": packages}
    manifest = {
        "task": "arrange-workspace",
        "tool": "local-python-execute",
        "upstream": str(UPSTREAM.relative_to(REPO_ROOT)),
        "pyodide": version,
        "requested": list(WANTED),
        "packages": sources,
    }
    for filename, content in (("pyodide-lock.json", lock), ("manifest.json",
                                                            manifest)):
        target = DEST / filename
        serialized = json.dumps(content, indent=1) + "\n"
        if args.check:
            if not target.is_file() or target.read_text() != serialized:
                print(f"MISSING or STALE {filename}")
                missing += 1
        else:
            target.write_text(serialized)
    print(
        f"{len(WANTED)} task packages, {len(packages)} including dependencies")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
