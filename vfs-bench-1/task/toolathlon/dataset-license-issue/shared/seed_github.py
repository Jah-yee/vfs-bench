#!/usr/bin/env python
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures"
NAME = HERE.parent.name
PROJECT = "Annoy-DataSync"
# The fake's own default login, which is who a comment is attributed to and
# who `GET /user` answers with. The evaluator compares the two.
LOGIN = "integ-user"
DEFAULT_URL = "http://127.0.0.1:19801"
# Upstream's preprocess, verbatim: the agent is answering this issue and the
# evaluator reads back the thread under it.
TITLE = "License info. needed"
BODY = ("Thanks for sharing this project! Could you provide license info. "
        "for Annoy-PyEdu-Rs-Raw and Annoy-PyEdu-Rs? thanks!")

sys.path.insert(0, str(REPO / "server" / "fakes"))
sys.path.insert(0, str(REPO / "agent"))

import github  # noqa: E402
from services import ground_truth  # noqa: E402


def resolved(work: Path) -> Path:
    """The vendored project with its two namespace placeholders filled in.

    The repository ships `{github_namespace}` and `{hf_namespace}` in its
    README and upstream's preprocess rewrites them once the real logins are
    known. Doing it here rather than in `build_fixture.py` is what keeps the
    committed tree a verbatim copy of the commit it names: the fixture is
    the project, and whose account it was pushed to is this run's fact.

    Args:
        work (Path): scratch directory.

    Returns:
        Path: the substituted tree.
    """
    into = work / PROJECT
    shutil.copytree(FIXTURE / PROJECT, into)
    swaps = {"{github_namespace}": LOGIN, "{hf_namespace}": NAME}
    for path in into.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for placeholder, value in swaps.items():
            text = text.replace(placeholder, value)
        path.write_text(text, encoding="utf-8")
    return into


def open_issue(url: str, full_name: str) -> int:
    """File the issue the ask is a reply to.

    A fixture row states a repository and its files; it has no column for
    an issue, so this goes over the same REST call a client would make.

    Args:
        url (str): the fake's base URL.
        full_name (str): `owner/repo`.

    Returns:
        int: the issue number, which the evaluator looks the thread up by.
    """
    made = github.call(url, f"/repos/{full_name}/issues", {
        "title": TITLE,
        "body": BODY
    })
    return int(made["number"])


def head_sha(url: str, full_name: str) -> str:
    """The commit the repository is at, which the evaluator pins.

    A run whose HEAD moved is failed outright -- the ask is to comment and
    close, not to push -- so this is recorded at seed time and compared
    against afterwards.

    Args:
        url (str): the fake's base URL.
        full_name (str): `owner/repo`.

    Returns:
        str: the sha.

    Raises:
        SystemExit: the repository has no commits.
    """
    rows = github.call(url, f"/repos/{full_name}/commits", method="GET")
    listed = rows if isinstance(rows, list) else []
    if not listed:
        sys.exit(f"{full_name} seeded with no commits")
    return str(listed[0]["sha"])


def record(full_name: str, number: int, sha: str) -> Path:
    """Write the answer sheet the evaluator opens.

    Upstream's preprocess writes this file, because every value in it is
    invented by the run: which account the repository landed under, which
    number the issue got, what the head was at the time. Ours are different
    values for the same reasons, so upstream's committed copy -- which
    names `toolathlon-testuser` and a sha from their machine -- describes
    nothing here.

    The two Hub URLs are stated rather than looked up: `seed_hf.py` seeds
    those two repositories under this same namespace, and having one writer
    for this file is worth more than having each half report itself.

    Args:
        full_name (str): `owner/repo`.
        number (int): the issue number.
        sha (str): the head commit.

    Returns:
        Path: the file written.
    """
    where = ground_truth(NAME)
    where.mkdir(parents=True, exist_ok=True)
    path = where / "task_state.json"
    path.write_text(json.dumps(
        {
            "github_repo": full_name,
            "issue_number": number,
            "issue_url": (f"https://github.com/{full_name}/issues/"
                          f"{number}"),
            "hf_datasets": {
                "reasoning": (f"https://huggingface.co/datasets/{NAME}/"
                              f"Annoy-PyEdu-Rs"),
                "raw": (f"https://huggingface.co/datasets/{NAME}/"
                        f"Annoy-PyEdu-Rs-Raw"),
            },
            "latest_commit_hash": sha,
        },
        indent=2) + "\n",
                    encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",
                        default=os.environ.get("GITHUB_URL", DEFAULT_URL))
    args = parser.parse_args()
    if not (FIXTURE / PROJECT).is_dir():
        sys.exit(f"no fixture for {PROJECT} under {FIXTURE}; "
                 f"see shared/build_fixture.py")
    full_name = f"{LOGIN}/{PROJECT}"
    with tempfile.TemporaryDirectory() as tmp:
        source = github.stage(f"{NAME}-{PROJECT}", resolved(Path(tmp)))
    github.write(
        NAME,
        [github.repo(full_name, source_dir=source)],
        # `github_allowed_repos = "Annoy-DataSync"`, and the fork's server
        # disables repository creation outright whenever that is set. The
        # MCP arm therefore cannot create one, so neither may the other.
        create_repos=False)
    github.reset(args.url, NAME, note=full_name)
    number = open_issue(args.url, full_name)
    path = record(full_name, number, head_sha(args.url, full_name))
    print(f"github: issue #{number} on {full_name}, state in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
