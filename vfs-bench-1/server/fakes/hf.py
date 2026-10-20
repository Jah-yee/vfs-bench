import hashlib
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "agent"))

from services import stack_dir  # noqa: E402

# The client side of mirage's Hugging Face Hub fake, which is a kit fake: a
# task writes a fixture into the assembled root and asks for it by name, the
# way it does for notion and github.
SERVICE = "hf-hub"


def root() -> Path:
    """Where this repo's Hub fixtures live.

    `server/fakes/stack.py` assembles the root and the fake is launched
    against it with `--fixture-root`.

    Returns:
        Path: the hf-hub fixture directory, created if absent.
    """
    into = stack_dir() / "integ" / SERVICE
    into.mkdir(parents=True, exist_ok=True)
    return into


def stage(name: str, files: dict[str, Path]) -> str:
    """Put one repository's files in, and name them the way a row does.

    Args:
        name (str): a directory name, unique within the fixture.
        files (dict[str, Path]): path inside the repository to its source
            on disk. A repository's content is copied rather than linked,
            because the fake reads it server-side.

    Returns:
        str: the value a repo row's `sourceDir` takes, which the fake
            resolves against the fixture ROOT and so carries the service
            directory in front of it.
    """
    target = root() / name
    if target.exists():
        shutil.rmtree(target)
    for inside, source in sorted(files.items()):
        into = target / inside
        into.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, into)
    return f"{SERVICE}/{name}"


def sha_of(repo_id: str) -> str:
    """The commit sha a seeded repository answers with.

    Derived from the id rather than stated, so two seedings of one fixture
    answer the same sha and a task that records one is not recording the
    order it was written in.

    Args:
        repo_id (str): `kind/namespace/name`.

    Returns:
        str: forty hex characters.
    """
    return hashlib.sha1(repo_id.encode()).hexdigest()


def repo(repo_id: str,
         kind: str = "datasets",
         source_dir: str = "",
         downloads: int = 0,
         likes: int = 0,
         created_at: str = "2025-01-01T00:00:00.000Z") -> dict:
    """One repository, as the three rows that describe it.

    Args:
        repo_id (str): `namespace/name`.
        kind (str): `models`, `datasets` or `spaces`, the plural the API
            path spells.
        source_dir (str): what `stage` returned, or "" for no files.
        downloads (int): the Hub's own counter, which `sort=downloads`
            orders on. A task asking for "the most downloaded" is asking
            about this column and nothing else.
        likes (int): the other counter.
        created_at (str): when the repository was created.

    Returns:
        dict: `repo`, `commit` and `ref` rows under those keys.
    """
    namespace, _, name = repo_id.partition("/")
    key = f"{kind}/{namespace}/{name}"
    sha = sha_of(key)
    return {
        "repo": {
            "kind": kind,
            "namespace": namespace,
            "name": name,
            "sourceDir": source_dir,
            "downloads": downloads,
            "likes": likes,
            "createdAt": created_at,
        },
        "commit": {
            "repo": key,
            "sha": sha,
            "message": "initial commit",
            "createdAt": created_at,
        },
        "ref": {
            "repo": key,
            "refType": "branch",
            "name": "main",
            "sha": sha
        },
    }


def write(name: str, repos: list[dict]) -> Path:
    """Write one task's fixture under the name its reset will ask for.

    Args:
        name (str): the fixture name.
        repos (list[dict]): rows from `repo`.

    Returns:
        Path: the file written.
    """
    path = root() / f"{name}.json"
    body = {
        "repos": [entry["repo"] for entry in repos],
        "commits": [entry["commit"] for entry in repos],
        "refs": [entry["ref"] for entry in repos],
    }
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def call(url: str,
         path: str,
         body: object | None = None,
         method: str = "POST",
         tenant: str = "default") -> dict:
    """One JSON request against the fake.

    Args:
        url (str): the fake's base URL.
        path (str): path below it, leading slash included.
        body (object | None): the JSON body, or None.
        method (str): the HTTP verb.
        tenant (str): who to speak as. The bearer IS the tenant here, so a
            read of a task's own fixture has to name it.

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
    request.add_header("Authorization", f"Bearer {tenant}")
    try:
        with urllib.request.urlopen(request, timeout=600) as reply:
            raw = reply.read()
    except urllib.error.HTTPError as raised:
        detail = raised.read().decode(errors="replace")[:400]
        raise SystemExit(f"hf-hub fake refused {method} {path}: "
                         f"{raised.code} {detail}") from raised
    except (urllib.error.URLError, OSError) as raised:
        raise SystemExit(f"no hf-hub fake at {url}{path} ({raised}); "
                         f"start it with bin/start.sh up") from raised
    return json.loads(raw) if raw else {}


def reset(url: str, name: str, note: str = "") -> dict:
    """Seed the fake from one of the fixtures in the root.

    The tenant is the task, not the default one. That is what the bearer
    selects on this fake, so both arms have to send it: the MCP arm's
    bridge carries `Authorization: Bearer <task>` and the mirage arm's
    mount carries the same string as its token. Seeding the default tenant
    instead leaves both arms authenticated as somebody with an empty Hub,
    which reads as a repository that does not exist rather than as an
    error.

    Args:
        url (str): the fake's base URL.
        name (str): the fixture name, which `write` created. Also the
            tenant, because a task's fixture is a task's alone.
        note (str): appended to the line printed on success.

    Returns:
        dict: the reply, whose `seeded` names the rows per table.
    """
    reply = call(url, "/reset", {"tenants": [name], "fixture": name})
    if not reply.get("ok"):
        raise SystemExit(f"hf-hub reset refused: {reply}")
    rows = reply.get("seeded", [{}])[0].get("rows", {})
    print(f"hf-hub: seeded {name} ({rows.get('HfRepo', 0)} repositories)"
          f"{': ' + note if note else ''}")
    return reply
