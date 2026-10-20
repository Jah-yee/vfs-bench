import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEST = REPO_ROOT / "vendor" / "wheels"
PYPI = "https://pypi.org/pypi"

# What 29 of this dataset's tasks import and pyodide does not carry, pinned
# by content rather than by version: PyPI promises a (name, version, tag) is
# immutable, and a sha256 does not need the promise. Every other install
# here pins its tree the same way -- `package-lock.json` for the five npm
# servers, `uv.lock` for the two Python ones.
#
# Every one is pure Python, which is why they can be mounted rather than
# built: the runtime imports a wheel off `/opt/wheels` in place, since a
# wheel is a zip and zipimport reads it where it lies. A C extension cannot
# come this way and goes through `setup_pyodide_packages.py` instead.
WHEELS = {
    # The serializer pdf-tools-mcp uses, from its pinned upstream lock.
    "pypdf2":
    ("3.0.1", "pypdf2-3.0.1-py3-none-any.whl",
     "d16e4205cfee272fbdc0568b68d82be796540b1537508cef59388f839c191928"),
    "et_xmlfile": ("2.0.0", "et_xmlfile-2.0.0-py3-none-any.whl",
                   "7a91720bc756843502c3b7504c77b8fe44217c85c537d85037f0f5"
                   "36151b2caa"),
    "openpyxl": ("3.1.5", "openpyxl-3.1.5-py2.py3-none-any.whl",
                 "5282c12b107bffeef825f4617dc029afaf41d0ea60823bbb665ef307"
                 "9dc79de2"),
    "pypdf": ("6.15.0", "pypdf-6.15.0-py3-none-any.whl",
              "14e001d6504822cb1ca9c7ed9a69bccb320f59b320730f55af804361abe"
              "4d5ee"),
    "python-docx": ("1.2.0", "python_docx-1.2.0-py3-none-any.whl",
                    "3fd478f3250fbbbfd3b94fe1e985955737c145627498896a8a6bf8"
                    "1f4baf66c7"),
    "python-pptx": ("1.0.2", "python_pptx-1.0.2-py3-none-any.whl",
                    "160838e0b8565a8b1f67947675886e9fea18aa5e795db7ae531606"
                    "d68e785cba"),
    "typing-extensions":
    ("4.16.0", "typing_extensions-4.16.0-py3-none-any"
     ".whl", "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3"
     "f350d78d6370c2e8"),
    "xlsxwriter": ("3.2.9", "xlsxwriter-3.2.9-py3-none-any.whl",
                   "9a5db42bc5dff014806c58a20b9eae7322a134abb6fce3c92c181bf"
                   "b275ec5b3"),
}


def digest(path: Path) -> str:
    """The sha256 of a file.

    Args:
        path (Path): the file.

    Returns:
        str: the hex digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def url_for(name: str, version: str, wheel: str) -> str:
    """Ask PyPI where one wheel lives.

    The download host is a CDN whose path carries a hash of the file, so it
    cannot be spelled here without pinning twice. The index is asked for it
    and the answer is checked against the digest below, which is the pin.

    Args:
        name (str): the distribution name.
        version (str): the exact version.
        wheel (str): the wheel filename.

    Returns:
        str: the download URL.

    Raises:
        SystemExit: the index does not offer that file.
    """
    import json

    with urllib.request.urlopen(f"{PYPI}/{name}/{version}/json") as reply:
        release = json.load(reply)["urls"]
    for entry in release:
        if entry["filename"] == wheel:
            return entry["url"]
    raise SystemExit(f"{name} {version} does not publish {wheel}")


def main() -> int:
    """Download the wheels, or report what is missing or wrong.

    Returns:
        int: process exit status.
    """
    ap = argparse.ArgumentParser(
        description="Vendor the pure-Python wheels the mirage arm mounts "
        "at /opt/wheels.")
    ap.add_argument("--check",
                    action="store_true",
                    help="verify what is present without downloading")
    args = ap.parse_args()

    DEST.mkdir(parents=True, exist_ok=True)
    problems = 0
    for name, (version, wheel, want) in sorted(WHEELS.items()):
        target = DEST / wheel
        if target.is_file():
            got = digest(target)
            if got == want:
                print(f"have    {name:18} {wheel}")
                continue
            # Not repaired silently: a wheel whose bytes moved under a
            # pinned name is the thing the digest is here to catch, and
            # overwriting it would erase the evidence.
            print(f"WRONG   {name:18} {wheel}\n"
                  f"        want sha256:{want}\n"
                  f"        got  sha256:{got}")
            problems += 1
            continue
        if args.check:
            print(f"MISSING {name:18} {wheel}")
            problems += 1
            continue
        print(f"fetch   {name:18} {wheel}")
        with urllib.request.urlopen(url_for(name, version, wheel)) as reply:
            body = reply.read()
        got = hashlib.sha256(body).hexdigest()
        if got != want:
            print(f"        refused: sha256:{got} is not sha256:{want}")
            problems += 1
            continue
        target.write_bytes(body)
        print(f"        {len(body) / 1e3:.0f} kB")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
