#!/usr/bin/env python
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LOCAL = REPO / "task" / "toolathlon"

DEEPSEEK_LICENSE_REVISION = "da42dcd40b41803c68a712ddd210eeb10e71e598"
DEEPSEEK_LICENSE_LINK = (
    "https://github.com/deepseek-ai/DeepSeek-V2/blob/main/LICENSE-MODEL")
DEEPSEEK_LICENSE_PINNED = ("https://github.com/deepseek-ai/DeepSeek-V2/blob/"
                           f"{DEEPSEEK_LICENSE_REVISION}/LICENSE-MODEL")
DEEPSEEK_LICENSE_RAW = (
    "https://raw.githubusercontent.com/deepseek-ai/DeepSeek-V2/"
    f"{DEEPSEEK_LICENSE_REVISION}/LICENSE-MODEL")
# What each task's agent is expected to look at.
SOURCES = {
    # Deliberately empty. `course-schedule` declares the fetch server in its
    # task_config and never needs it -- everything it asks about is in the
    # workspace -- but declaring it is what puts four more tool schemas in
    # front of the MCP arm on every request, so the server is mounted and
    # the arm pays for it. An empty capture means any URL an agent tries
    # misses and says so, rather than quietly reaching the internet.
    "course-schedule": [],
    # Empty for the same reason. `verl-dataset` declares the fetch server
    # and reaches the Hub through the huggingface server and its own
    # `python_execute` instead; what the declaration buys is four more tool
    # schemas in front of the MCP arm on every request, which it pays for
    # upstream and pays for here.
    "verl-dataset": [],
    # The DeepSeek card names the first URL exactly. Capture that lookup and
    # the same file at the commit where LICENSE-MODEL last changed, both as
    # GitHub renders it and as its immutable raw bytes. Runs stay sealed,
    # while either arm has the evidence upstream's live fetch server exposes.
    "dataset-license-issue": [
        DEEPSEEK_LICENSE_LINK,
        DEEPSEEK_LICENSE_PINNED,
        DEEPSEEK_LICENSE_RAW,
    ],
}
# The server sends this and some hosts vary on it, so the capture is taken
# through the same one the agent's requests will carry.
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
TIMEOUT = 30


def fixture_path(task: str) -> Path:
    """Where a task's capture lives.

    Args:
        task (str): the task directory name.
    """
    return LOCAL / task / "shared" / "web_fixture.json"


def get(url: str) -> dict:
    """Fetch one URL, keeping the status even when it is an error.

    A 404 is data here, not a failure: the capture carries a missing
    page's status and body the way the live site serves them.

    Args:
        url (str): the URL to record.

    Returns:
        dict: `status`, `content_type` and the response `body` as text.
    """
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as reply:
            status, raw, headers = reply.status, reply.read(), reply.headers
    except urllib.error.HTTPError as error:
        status, raw, headers = error.code, error.read(), error.headers
    return {
        "status": status,
        "content_type": headers.get("Content-Type", ""),
        "body": raw.decode("utf-8", errors="replace"),
    }


def summarise(url: str, entry: dict) -> str:
    """One line describing a captured response.

    Args:
        url (str): the URL.
        entry (dict): its captured response.
    """
    return f"{entry['status']} {len(entry['body']):>7} bytes  {url}"


def main() -> int:
    """Capture or check one task's responses."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(SOURCES))
    ap.add_argument("--check",
                    action="store_true",
                    help="re-fetch and report drift without writing")
    args = ap.parse_args()

    fresh = {url: get(url) for url in SOURCES[args.task]}
    path = fixture_path(args.task)

    if args.check:
        if not path.is_file():
            print(f"no capture at {path}", file=sys.stderr)
            return 1
        stored = json.loads(path.read_text())
        moved = 0
        for url, entry in fresh.items():
            was = stored.get(url)
            if was is None:
                print(f"NEW    {summarise(url, entry)}")
                moved += 1
            elif was["body"] != entry["body"]:
                print(f"MOVED  {summarise(url, entry)} "
                      f"(was {len(was['body'])} bytes)")
                moved += 1
            else:
                print(f"same   {summarise(url, entry)}")
        print(f"{moved} of {len(fresh)} responses have changed")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n")
    for url, entry in fresh.items():
        print(summarise(url, entry))
    print(f"wrote {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
