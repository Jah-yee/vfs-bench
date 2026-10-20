import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEST = REPO / "vendor" / "github-mcp-server"
SOURCE = "https://github.com/lockon-n/github-mcp-server"
# The commit Toolathlon's local_binary/github-mcp-version.txt names.
COMMIT = "ef07feb90b95893767c106067868735d9f550ba6"


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def patch_ghes_port(checkout: Path) -> None:
    """Let `--gh-host` keep its port.

    `newGHESHost` builds the REST, GraphQL, upload and raw URLs from
    `u.Hostname()`, which strips the port -- upstream says so in a comment
    directly above `parseAPIHost`: "Note that this does not handle ports yet,
    so development environments are out." A fake on 127.0.0.1:19801 is exactly
    the development environment that rules out, and the alternative is
    binding the fake to port 80 as root.

    `u.Host` is the same string with the port kept, so this is the whole fix.
    It touches URL construction only: no tool is added, removed or renamed, so
    the surface the MCP arm is measured on is still upstream's.

    Args:
        checkout (Path): the github-mcp-server source tree.
    """
    target = checkout / "internal" / "ghmcp" / "server.go"
    body = target.read_text()
    start = body.index("func newGHESHost(")
    end = body.index("\n}\n", start) + 3
    block = body[start:end]
    if "u.Hostname()" not in block:
        return
    body = body[:start] + block.replace("u.Hostname()", "u.Host") + body[end:]
    target.write_text(body)
    print("+ patched newGHESHost to keep the port")


def main() -> int:
    if shutil.which("go") is None:
        print("go not found on PATH; `brew install go`", file=sys.stderr)
        return 1
    DEST.mkdir(parents=True, exist_ok=True)
    checkout = DEST / "src"
    if not (checkout / ".git").exists():
        shutil.rmtree(checkout, ignore_errors=True)
        run(["git", "clone", SOURCE, str(checkout)], REPO)
    run(["git", "fetch", "origin", COMMIT], checkout)
    run(["git", "checkout", "--detach", COMMIT], checkout)

    patch_ghes_port(checkout)

    binary = DEST / "github-mcp-server"
    env = dict(os.environ, CGO_ENABLED="0")
    print("+ go build", flush=True)
    subprocess.run(
        ["go", "build", "-o",
         str(binary), "./cmd/github-mcp-server"],
        cwd=checkout,
        env=env,
        check=True)
    print(f"built {binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
