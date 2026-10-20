#!/usr/bin/env python
import argparse
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "agent"))
# The root, for the `server` package a dataset's hooks import: `used()`
# calls toolathlon's `needs_stack`, which reads `server.seed.research`.
sys.path.insert(0, str(REPO))

import dataset  # noqa: E402
from services import holding, stack_dir  # noqa: E402

COMPOSE = REPO / "docker" / "compose.yml"
_image_ready = False
# The compose services this process has reconciled, each once: the runner
# and the seed both bring a draw's services up.
_started: set[str] = set()
# Which of the stack's services each MCP server and each fixture kind
# reaches. A draw holds, starts, and its seed resets, exactly the ones its
# task names: every other service belongs to whichever draws are using it. The
# Forms server is absent on purpose -- the two tasks that declare it run
# their own Forms fake, not the stack's.
SERVER_SERVICES = {
    "google_sheet": "gws",
    "google_calendar": "gws",
    "github": "github",
    "notion": "notion",
    "huggingface": "hf",
    "emails": "mail",
    "snowflake": "postgres",
    "google-cloud": "gcp",
}
FIXTURE_SERVICES = {
    "mail": "mail",
    "bigquery": "gcp",
    "storage": "gcp",
    "logging": "gcp",
}
# The port each service is published on, which is what tells one stack's
# service from another's on the same host. Mail has no variable: tasks and
# upstream graders spell 1143 themselves, so every stack's mail tasks meet
# on that one port whatever MAIL_IMAP_PORT says.
SERVICE_PORTS = {
    "gws": ("GWS_PORT", "19999"),
    "github": ("GITHUB_PORT", "19801"),
    "notion": ("NOTION_PORT", "5091"),
    "hf": ("HF_HUB_PORT", "5199"),
    "mail": (None, "1143"),
    "postgres": ("PG_PORT", "5433"),
    "gcp": ("BQ_PORT", "9050"),
}
# The compose services that serve each of them. gcp's emulators are
# `server/fakes/gcp.py`'s to start; `api` is its Cloud Logging.
CONTAINERS = {
    "gws": ("gws", ),
    "github": ("github", ),
    "notion": ("notion", ),
    "hf": ("hfhub", ),
    "mail": ("mail", ),
    "postgres": ("postgres", ),
    "gcp": ("api", ),
}
# The directories of the fixture root each one's fake reads. The last three
# of hf's name no service: they are the shared file trees mirage's targets
# mount, and only hf-hub's fixture reads them here, seeding its blobs out of
# them by `sourceDir`.
FIXTURE_TREES = {
    "gws": ("gws", ),
    "notion": ("notion", ),
    "github": ("github", ),
    "hf": ("hf-hub", "hf-mcp", "columnar", "files", "hf-cards"),
}


def compose(*args: str, **kwargs):
    """Run docker compose against this stack.

    Args:
        *args (str): the compose subcommand and its arguments.
        **kwargs: passed to `subprocess.run`.

    Returns:
        subprocess.CompletedProcess: the finished command.
    """
    return subprocess.run(["docker", "compose", "-f",
                           str(COMPOSE), *args],
                          env={
                              **os.environ, "REPO_ROOT": str(REPO),
                              "STACK_DIR": str(stack_dir())
                          },
                          **kwargs)


def pending(containers: list[str] | None = None) -> int:
    """How many containers are not yet healthy.

    Health is asked of docker rather than probed here, so a service that
    reports itself healthy and a service this file calls healthy can never
    disagree.

    Args:
        containers (list[str] | None): the compose services to ask about;
            the whole project's when None.

    Returns:
        int: containers still starting; 0 when they are ready.
    """
    ids = compose("ps",
                  "-q",
                  *(containers or []),
                  capture_output=True,
                  text=True).stdout.split()
    if not ids:
        return 1
    waiting = 0
    for one in ids:
        done = subprocess.run([
            "docker", "inspect", "-f",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
            one
        ],
                              capture_output=True,
                              text=True)
        if done.stdout.strip() not in ("healthy", "none"):
            waiting += 1
    return waiting


def used(task: str) -> list[str]:
    """The stack services one task's draw reaches.

    What it holds for the length of the draw and what its seed empties,
    read off the task's own declarations: the MCP servers it names and the
    fixtures its manifest builds. Nothing, for a task whose services are
    all its own.

    Args:
        task (str): the task name.

    Returns:
        list[str]: service names from `SERVER_SERVICES`, sorted.
    """
    decide = getattr(dataset, "needs_stack", None)
    if not (decide(task) if decide else getattr(dataset, "NEEDS_STACK", True)):
        return []
    found = {
        SERVER_SERVICES[name]
        for name in dataset.needed_mcp_servers(task) if name in SERVER_SERVICES
    }
    manifest = getattr(dataset, "manifest", None)
    if manifest and manifest(task).is_file():
        fixtures = json.loads(manifest(task).read_text(encoding="utf-8"))
        found |= {
            FIXTURE_SERVICES[entry["kind"]]
            for entry in fixtures["fixtures"]
            if entry["kind"] in FIXTURE_SERVICES
        }
    return sorted(found)


def locks(task: str) -> list[str]:
    """The host locks for the stack services one task's draw reaches.

    Args:
        task (str): the task name.

    Returns:
        list[str]: one name per service, naming the stack by its port.
    """
    names = []
    for service in used(task):
        variable, default = SERVICE_PORTS[service]
        port = os.environ.get(variable, default) if variable else default
        names.append(f"stack-{service}-{port}")
    return names


def sync(source: Path, into: Path) -> None:
    """Make one tree hold what another holds, a file at a time.

    Every file lands by rename, so a fake reading one while another draw's
    stack comes up sees the old bytes or the new ones and never a gap, and
    a file that has not changed is not touched at all.

    Only a file an earlier sync put there and the source no longer has is
    removed, which is what `.assembled` records. Seeders write into this
    tree too -- a GitHub or Hub task stages its repositories under the
    service's directory and resets the fake from them -- and those files
    must outlive another draw's stack coming up in the middle of that seed.

    Args:
        source (Path): the tree to copy, on the same filesystem as `into`;
            its files are moved rather than copied.
        into (Path): the tree to update.
    """
    into.mkdir(parents=True, exist_ok=True)
    record = into / ".assembled"
    previous = set(json.loads(
        record.read_text())) if record.is_file() else set()
    wanted = set()
    for path in sorted(source.rglob("*")):
        target = into / path.relative_to(source)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        wanted.add(str(path.relative_to(source)))
        if not (target.is_file() and filecmp.cmp(path, target, shallow=False)):
            os.replace(path, target)
    for gone in previous - wanted:
        (into / gone).unlink(missing_ok=True)
    staged = into / f".assembled.{os.getpid()}"
    staged.write_text(json.dumps(sorted(wanted)))
    os.replace(staged, record)


def assemble_fixtures(services: list[str] | None = None) -> Path:
    """Build the fixture root both kit fakes are launched against.

    A fixture is a NAME on the kit, resolved under `<root>/<service>/`, and
    the root is now the operator's to choose (`--fixture-root`). That is what
    this builds: mirage's own fixtures copied out of the pinned submodule so
    a fake can seed at startup, and this repo's beside them under names the
    seeders ask for.

    All three kit fakes read it, including gws, which this repo overrides
    nothing for. One rule beats two: gws became a kit fake in the same pass
    that moved it onto Prisma, so it now dies at startup without a fixture,
    and a second mechanism for the one service we do not override would be a
    thing to remember rather than a thing to read.

    On the shared volume rather than in the image, so editing a task's
    fixture is a file write and not a rebuild -- and as a directory tree
    rather than a set of file mounts, because a github repository's files
    come from a `sourceDir` the fake walks.

    Built beside the root and then synced into it, rather than into it
    directly: every draw that needs the stack rebuilds it, and another
    draw's seed may be resetting a fake from it at that moment. Removing a
    service's directory to copy it back left that reset a window with no
    fixture to read.

    Only the trees of the services asked for, each synced on its own: a
    draw holds its own services' locks, and any other tree may be under a
    draw beside it that seeded from another checkout's copy.

    Args:
        services (list[str] | None): names from `SERVICE_PORTS`, as `used`
            gives them; every one when None.

    Returns:
        Path: the assembled root, as the host sees it.
    """
    trees = [
        tree for service in (SERVICE_PORTS if services is None else services)
        for tree in FIXTURE_TREES.get(service, ())
    ]
    root = stack_dir() / "integ"
    root.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=".integ-", dir=root.parent))
    try:
        upstream = REPO / "submodule" / "mirage" / "integ" / "fixtures"
        # Upstream's own trees; authoring a substitute would fork bytes
        # upstream already states.
        for tree in trees:
            into = staged / tree
            into.mkdir(parents=True, exist_ok=True)
            # Copied per run rather than once: bumping the submodule moves
            # these, and a stale copy would be a fixture nobody could trace
            # to a pin.
            source = upstream / tree
            for entry in sorted(source.iterdir()) if source.is_dir() else []:
                target = into / entry.name
                if entry.is_dir():
                    shutil.copytree(entry, target)
                else:
                    shutil.copy2(entry, target)

        if "notion" in trees:
            # notion ships no `empty.json` of its own, so the name `reset`
            # asks for is this repo's file. github ships one and it is left
            # alone.
            shutil.copy2(REPO / "server" / "clients" / "notion_empty.json",
                         staged / "notion" / "empty.json")
            for task in dataset.tasks():
                rows = dataset.local(task) / "shared" / "notion_rows.json"
                if rows.is_file():
                    shutil.copy2(rows, staged / "notion" / f"{task}.json")
        for tree in trees:
            sync(staged / tree, root / tree)
    finally:
        shutil.rmtree(staged, ignore_errors=True)
    return root


def up(services: list[str] | None = None, timeout: int | None = None) -> None:
    """Bring the always-on fakes up and wait for them.

    Build the shared fixture image once per host process, then reconcile the
    running services with that image. Docker's layer cache keeps an unchanged
    checkout cheap, while the build prevents a healthy container from serving
    older code than the source recorded in run provenance.

    Only the services asked for, which for a draw are the ones it holds.
    Every checkout shares this project but mounts its own `REPO_ROOT` and
    `STACK_DIR`, so a project-wide `compose up` from one recreates every
    container a draw from another is using -- and so does an image built
    from other code.

    Args:
        services (list[str] | None): names from `SERVICE_PORTS`, as `used`
            gives them; every one when None, which is `bin/start.sh up`.
        timeout (int | None): seconds to wait, default `STACK_TIMEOUT`.

    Raises:
        SystemExit: the stack did not become healthy.
    """
    wanted = list(SERVICE_PORTS) if services is None else list(services)
    if not wanted:
        return
    containers = [name for service in wanted for name in CONTAINERS[service]]
    # Before the containers, not after: both kit fakes seed at startup from
    # a fixture under this root, and a fake whose root has no such name dies
    # with a FixtureError instead of coming up empty.
    #
    # One startup at a time per stack, because draws starting together each
    # get here: the image tag is the project's, so one checkout's build must
    # not land between another's build and the `compose up` that starts
    # containers from it.
    global _image_ready
    project = os.environ.get("COMPOSE_PROJECT_NAME", "toolathlon")
    with holding([f"stack-up-{project}"]):
        assemble_fixtures(wanted)
        fresh = [name for name in containers if name not in _started]
        if fresh:
            if not _image_ready:
                compose("build", "api", check=True)
                _image_ready = True
            compose("up", "-d", "--no-deps", *fresh, check=True)
            _started.update(fresh)
    if pending(containers) == 0:
        return
    limit = timeout or int(os.environ.get("STACK_TIMEOUT", "180"))
    deadline = time.time() + limit
    while time.time() < deadline:
        if pending(containers) == 0:
            return
        time.sleep(2)
    compose("ps", "--format", "  {{.Service}}\t{{.Status}}")
    raise SystemExit(f"stack did not become healthy in {limit}s")


def post(url: str, body: dict | None = None) -> None:
    """POST to a fake's reset endpoint, or stop the seed.

    A reset that did not happen leaves the previous draw's state in front
    of this one, so a fake that is down, drops the connection or refuses
    the body stops the seed rather than letting the draw run on. It used
    to be ignored, which is how github's reset went unnoticed while every
    seed sent a body the fake refused with a 400.

    Args:
        url (str): the endpoint.
        body (dict | None): the JSON body, or none at all.

    Raises:
        SystemExit: the reset did not happen.
    """
    data = json.dumps(body).encode() if body is not None else None
    headers = {"content-type": "application/json"} if body is not None else {}
    request = urllib.request.Request(url,
                                     data=data,
                                     headers=headers,
                                     method="POST")
    try:
        urllib.request.urlopen(request, timeout=30).close()
    except urllib.error.HTTPError as raised:
        detail = raised.read(400).decode("utf-8", "replace")
        raise SystemExit(f"reset refused at {url}: {raised.code} "
                         f"{detail}") from raised
    except (urllib.error.URLError, OSError) as raised:
        raise SystemExit(f"no reset at {url} ({raised})") from raised


def notion_workspaces(task: str | None = None) -> list[str]:
    """The notion workspaces one task names, or every task in the dataset.

    Args:
        task (str | None): the task, or None for all of them.

    Returns:
        list[str]: workspace names, sorted and unique.
    """
    found = set()
    for one in [task] if task else dataset.tasks():
        named = dataset.local(one) / "shared" / "notion.json"
        if named.is_file():
            found.add(
                json.loads(named.read_text(encoding="utf-8"))["workspace"])
    return sorted(found)


def reset(task: str | None = None, services: list[str] | None = None) -> None:
    """Empty the stack services one draw reaches, and only those.

    Run before a task's fixtures are built, and not redundant with them: a
    task's manifest restores what it declares, and what it cannot restore
    is state the *previous* draw left in a service this one uses. A service
    this task does not use is left alone, because draws now run side by
    side and it belongs to whichever draw is using it. With no task, every
    service and every task's corner of it, which is what an operator
    emptying the stack by hand means.

    The bodies are not interchangeable. github needs its seed named,
    because an empty body means "replay whatever you were last seeded
    with", which is the previous task's repositories -- and a body naming a
    field the kit does not know is refused with a 400 that `post` swallows,
    which is how `{"repo": []}` left github unreset for as long as it was
    sent. gws takes an empty object; GreenMail takes no body at all.

    Args:
        task (str | None): the task whose draw is being seeded.
        services (list[str] | None): the services to empty, from `used`;
            None for all of them.
    """
    port = os.environ.get
    wanted = set(SERVICE_PORTS if services is None else services)
    emptied = []
    for name, url, body in (
        ("gws", f"http://127.0.0.1:{port('GWS_PORT', '19999')}/reset", {}),
        ("github", f"http://127.0.0.1:{port('GITHUB_PORT', '19801')}/reset", {
            "fixture": "empty"
        }),
        ("mail", f"http://127.0.0.1:{port('MAIL_API_PORT', '8081')}"
         "/api/service/reset", None),
    ):
        if name in wanted:
            post(url, body)
            emptied.append(name)

    # notion is keyed by workspace: a bearer token *is* a tenant on that
    # fake, so there is no global reset to call -- five tasks share the one
    # process. Emptying it means emptying each workspace by name, against a
    # fixture with nothing in it; without the fixture the kit falls back to
    # `v1`, which is mirage's own demo content, not empty.
    #
    # A restart is not the alternative it looks like, and never was. The old
    # server named its SQLite after a pid that is constant in a container, so
    # every restart reopened the previous database; the kit does not put the
    # file anywhere the container owns at all -- it mkdtemp's a directory per
    # process -- so a restart now empties everything, including the other
    # four tasks nobody asked to reset.
    #
    # `empty` is a NAME, resolved inside the fake's own fixtures/notion/;
    # `assemble_fixtures` copies server/clients/notion_empty.json onto it.
    spaces = notion_workspaces(task) if "notion" in wanted else []
    for workspace in spaces:
        post(f"http://127.0.0.1:{port('NOTION_PORT', '5091')}/reset", {
            "tenants": [workspace],
            "fixture": "empty"
        })
    if spaces:
        emptied.append(f"{len(spaces)} notion workspace(s)")

    # The fake with no HTTP surface of its own: Cloud Logging is a
    # directory per task on the shared volume.
    if "gcp" in wanted:
        logs = stack_dir() / "cloud_logging"
        shutil.rmtree(logs / task if task else logs, ignore_errors=True)
        emptied.append("cloud logging")

    # github's launch arguments go too. Nothing restarts here, but the file
    # is read on *any* restart -- `stack.up`, or the `unless-stopped` policy
    # after a crash -- and left in place that restart hands back the
    # previous task's repositories and its `--no-create-repos`, which is a
    # seeded fake wearing the face of an empty one.
    if "github" in wanted:
        (stack_dir() / "github.argv").unlink(missing_ok=True)

    print(f"reset: {', '.join(emptied) or 'nothing this task uses'}")


def main() -> int:
    """Bring the stack up, or empty it, from the command line.

    Returns:
        int: process exit status.
    """
    parser = argparse.ArgumentParser(
        description="The always-on fakes: bring them up, or empty them.")
    parser.add_argument("action", choices=["up", "reset", "status"])
    args = parser.parse_args()
    if args.action == "up":
        up()
        compose("ps", "--format", "  {{.Service}}\t{{.Status}}")
    elif args.action == "reset":
        reset()
    else:
        compose("ps", "--format", "  {{.Service}}\t{{.Status}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
