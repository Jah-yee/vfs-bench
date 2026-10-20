#!/usr/bin/env python
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# What the MCP arm's servers run in: upstream's own sandbox image, with the
# four servers it fetches from a GitHub branch at every start installed at a
# commit instead, and readabilipy's JavaScript installed before the fetch
# server's first page asks for it (`docker/mcpatlas.Dockerfile`). Each is a
# lock committed here:
#
# - github and weather, which upstream runs as `npx -y https://github.com/...`
#   -- no version at all, whatever the default branch holds -- pinned to the
#   commit each branch has held since 2025-07-24;
# - pubmed and weather-data, which it runs as `uvx --from git+...`, pinned to
#   a commit and resolved as of the image's build (their `pyproject.toml`s
#   say how);
# - readabilipy, which runs `npm install` in its own package on the first
#   fetch -- three ranges and no lock, resolved afresh in every container,
#   with npm's report on the server's stdout, which is the JSON-RPC stream.
#
# Every other server, and `/data`, is the image's own.
INPUTS = (
    "docker/mcpatlas.Dockerfile",
    "vendor/mcpatlas-mcp/github/package.json",
    "vendor/mcpatlas-mcp/github/package-lock.json",
    "vendor/mcpatlas-mcp/weather/package.json",
    "vendor/mcpatlas-mcp/weather/package-lock.json",
    "vendor/mcpatlas-mcp/pubmed/pyproject.toml",
    "vendor/mcpatlas-mcp/pubmed/uv.lock",
    "vendor/mcpatlas-mcp/weather-data/pyproject.toml",
    "vendor/mcpatlas-mcp/weather-data/uv.lock",
    "vendor/mcpatlas-mcp/fetch/readabilipy/package-lock.json",
)


def image_name() -> str:
    """The tag of the image these inputs build.

    Returns:
        str: a tag that moves whenever any input does.
    """
    digest = hashlib.sha256()
    for name in INPUTS:
        digest.update((REPO / name).read_bytes())
    return "vfs-bench-mcpatlas:" + digest.hexdigest()[:16]


def main() -> int:
    """Build the image from its inputs alone.

    Only the inputs are sent, never the checkout or its keys.

    Returns:
        int: process exit status.
    """
    with tempfile.TemporaryDirectory(prefix="mcpatlas-build-") as directory:
        context = Path(directory)
        for name in INPUTS:
            target = context / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / name, target)
        done = subprocess.run([
            "docker", "build", "--file",
            str(context / INPUTS[0]), "--tag",
            image_name(),
            str(context)
        ],
                              check=False)
    if done.returncode != 0:
        print(f"docker build failed ({done.returncode})", file=sys.stderr)
        return 1
    print(f"image: {image_name()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
