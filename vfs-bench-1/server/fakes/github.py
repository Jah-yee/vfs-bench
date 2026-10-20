import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "agent"))

from services import stack_dir  # noqa: E402

# The client side of mirage's github fake, which is a kit fake now rather
# than a Python process seeded from its own launch arguments.
#
# What that changed: seeding used to mean restarting the server with
# `--repo`, `--metadata`, `--commits` and `--no-create-repos`, because it
# held every repository in memory and a restart was the only way to empty
# it. Now it holds them in a per-run SQLite file and `POST /reset` seeds a
# named fixture, so the five tasks say the same things in a fixture this
# writes and, for what a fixture cannot state, over the git data API.
SERVICE = "github"


def root() -> Path:
    """Where this repo's github fixtures live.

    `server/fakes/stack.py` assembles the root and the fake is launched
    against it with `--fixture-root`; a task writes its own fixture in here
    before asking for it by name.

    Returns:
        Path: the github fixture directory, created if absent.
    """
    into = stack_dir() / "integ" / SERVICE
    into.mkdir(parents=True, exist_ok=True)
    return into


def stage(name: str, source: Path) -> str:
    """Copy one repository's files in, and name them the way a row does.

    Args:
        name (str): a directory name, unique within the fixture.
        source (Path): the tree to copy.

    Returns:
        str: the value a repo row's `sourceDir` takes, which the fake
            resolves against the fixture ROOT and so carries the service
            directory in front of it.
    """
    target = root() / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return f"{SERVICE}/{name}"


def repo(full_name: str,
         branch: str = "main",
         source_dir: str = "",
         meta: dict | None = None) -> dict:
    """One repository row.

    Args:
        full_name (str): `owner/name`.
        branch (str): its default branch, which is also the branch
            `source_dir` is loaded into unless `sourceBranch` says another.
        source_dir (str): what `stage` returned, or "" for no files.
        meta (dict | None): the vendor fields a fixture cannot otherwise
            carry -- description, stars, topics -- which the fake merges
            into the repository JSON it answers with.

    Returns:
        dict: the row.
    """
    owner, _, name = full_name.partition("/")
    row = {
        "fullName": full_name,
        "owner": owner,
        "name": name,
        "defaultBranch": branch,
        "sourceDir": source_dir,
    }
    if meta:
        row["metaJson"] = json.dumps(meta, ensure_ascii=False)
    return row


def write(name: str, repos: list[dict], create_repos: bool = True) -> Path:
    """Write one task's fixture under the name its reset will ask for.

    Args:
        name (str): the fixture name.
        repos (list[dict]): rows from `repo`.
        create_repos (bool): False is what `--no-create-repos` meant. Four
            tasks need it: upstream's token names its repositories, so its
            own server refuses `create_repository`, and an arm able to
            create one could reach a passing grade by a route the other
            arm does not have.

    Returns:
        Path: the file written.
    """
    path = root() / f"{name}.json"
    body = {"repos": repos, "settings": [{"createRepos": create_repos}]}
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def call(url: str,
         path: str,
         body: object | None = None,
         method: str = "POST") -> dict:
    """One JSON request against the fake.

    Args:
        url (str): the fake's base URL.
        path (str): path below it, leading slash included.
        body (object | None): the JSON body, or None.
        method (str): the HTTP verb.

    Returns:
        dict: the decoded reply, or {} for an empty one.

    Raises:
        SystemExit: the fake is not reachable, or refused.
    """
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(f"{url.rstrip('/')}{path}",
                                     data=data,
                                     method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", "Bearer seed")
    try:
        with urllib.request.urlopen(request, timeout=60) as reply:
            raw = reply.read()
    except urllib.error.HTTPError as raised:
        detail = raised.read().decode(errors="replace")[:400]
        raise SystemExit(f"github fake refused {method} {path}: "
                         f"{raised.code} {detail}") from raised
    except (urllib.error.URLError, OSError) as raised:
        raise SystemExit(f"no github fake at {url}{path} ({raised}); "
                         f"start it with bin/start.sh up") from raised
    return json.loads(raw) if raw else {}


def reset(url: str, name: str, note: str = "") -> dict:
    """Seed the fake from one of the fixtures in the root.

    Replaces `launch`: a restart no longer empties anything, because the
    kit puts each run's SQLite in a directory the container does not own.

    Args:
        url (str): the fake's base URL.
        name (str): the fixture name, which `write` created.
        note (str): appended to the line printed on success.

    Returns:
        dict: the reply, whose `seeded` names the rows per table.
    """
    reply = call(url, "/reset", {"fixture": name})
    if not reply.get("ok"):
        raise SystemExit(f"github reset refused: {reply}")
    rows = reply.get("seeded", [{}])[0].get("rows", {})
    print(f"github: seeded {name} "
          f"({rows.get('GithubRepo', 0)} repositories, "
          f"{rows.get('GithubFile', 0)} files)"
          f"{': ' + note if note else ''}")
    return reply


def branch(url: str, full_name: str, name: str, base: str) -> None:
    """Create a branch at another branch's head.

    A fixture states one branch per repository, because a repo row names
    one `sourceDir` and one branch to load it into. A task with several
    says the rest here, over the same git data API a client would use.

    Args:
        url (str): the fake's base URL.
        full_name (str): `owner/repo`.
        name (str): the branch to create.
        base (str): the branch whose head it starts at.
    """
    head = call(url, f"/repos/{full_name}/git/ref/heads/{base}", method="GET")
    call(url, f"/repos/{full_name}/git/refs", {
        "ref": f"refs/heads/{name}",
        "sha": head["object"]["sha"],
    })


def commit(url: str,
           full_name: str,
           on: str,
           files: dict[str, bytes],
           message: str,
           author: dict | None = None,
           replace: bool = False) -> str:
    """Add one commit to a branch, and move the branch to it.

    Args:
        url (str): the fake's base URL.
        full_name (str): `owner/repo`.
        on (str): the branch to commit on.
        files (dict[str, bytes]): path to content.
        replace (bool): whether the tree is these files ALONE. The fake the
            kit replaced seeded a named branch into an EMPTY tree, so a
            branch carried what its own fixture directory held and nothing
            from the branch it was cut off. Naming no `base_tree` is how
            that is said here; the default adds to what the branch has,
            which is what an overlay wants.
        message (str): the commit message.
        author (dict | None): `name`, `email` and `date`. Passed through
            because a task can turn on when a commit was made --
            `task-tracker` asks for "the most recent commits" -- and the
            fake would otherwise stamp its own clock.

    Returns:
        str: the new commit's sha.
    """
    head = call(url, f"/repos/{full_name}/git/ref/heads/{on}", method="GET")
    parent = head["object"]["sha"]
    # The tree is read by REF, not through the parent commit. A branch that
    # a fixture seeded has a synthetic root commit that
    # `GET /git/commits/:sha` does not serve, so resolving the base through
    # the parent 404s on the first commit of every seeded branch -- while
    # `GET /git/trees/:ref` answers for exactly the same tree.
    base = call(url, f"/repos/{full_name}/git/trees/{on}", method="GET")["sha"]
    tree = call(
        url, f"/repos/{full_name}/git/trees", {
            **({} if replace else {
                   "base_tree": base
               }),
            "tree": [{
                "path": path,
                "mode": "100644",
                "type": "blob",
                "content": data.decode("utf-8", errors="replace"),
            } for path, data in sorted(files.items())],
        })
    made = call(
        url, f"/repos/{full_name}/git/commits", {
            "message": message,
            "tree": tree["sha"],
            "parents": [parent],
            **({
                "author": author
            } if author else {}),
        })
    call(url,
         f"/repos/{full_name}/git/refs/heads/{on}", {"sha": made["sha"]},
         method="PATCH")
    return made["sha"]


def default_branch(url: str, full_name: str, name: str) -> None:
    """Point the repository's default branch at one of its branches.

    Seeding needs this because `POST /git/commits` records the commit
    against the repository's DEFAULT branch and not against the ref the
    caller afterwards moves -- deliberately, since that is what the python
    fake did. A task with per-branch history therefore writes each branch
    while it is the default one, and puts the real default back at the end.

    Args:
        url (str): the fake's base URL.
        full_name (str): `owner/repo`.
        name (str): the branch to make default.
    """
    call(url, f"/repos/{full_name}", {"default_branch": name}, method="PATCH")
