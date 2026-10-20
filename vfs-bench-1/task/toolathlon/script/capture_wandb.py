"""Capture public W&B experiment data, without consulting a grader."""
import base64
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory

import requests

REPO = Path(__file__).resolve().parents[3]
DEST = REPO / "task/toolathlon/shared/fixtures/wandb"
URL = "https://api.wandb.ai/graphql"
PROJECT = """query($entity:String!,$project:String!) {
 project(entityName:$entity,name:$project) {
 id internalId createdAt readOnly description runCount isBenchmark
 user { id name username email }
 }}"""
RUNS = """query($entity:String!,$project:String!,$cursor:String) {
 project(entityName:$entity,name:$project) {
 runs(first:100,after:$cursor,order:"+name") {
 edges { node {
 id projectId name displayName state tags sweepName group jobType
 commit readOnly
 createdAt heartbeatAt description notes user { id name username email }
 systemMetrics historyLineCount historyKeys fileCount config summaryMetrics
 }} pageInfo { endCursor hasNextPage }
 }}}"""
HISTORY = """query($entity:String!,$project:String!,$run:String!,
 $start:Int64!,$stop:Int64!,$samples:Int!) {
 project(entityName:$entity,name:$project) { run(name:$run) {
 history(minStep:$start,maxStep:$stop,samples:$samples)
 }}}"""
FILES = """query($entity:String!,$project:String!,
 $run:String!,$cursor:String) {
 project(entityName:$entity,name:$project) { run(name:$run) {
 files(first:100,after:$cursor) {
 edges { node { id name sizeBytes mimetype updatedAt directUrl md5 }}
 pageInfo { endCursor hasNextPage }
 }}}}"""


def query(session: requests.Session, text: str, variables: dict) -> dict:
    """Fetch a public GraphQL response; fail on partial/error results."""
    response = session.post(URL,
                            json={
                                "query": text,
                                "variables": variables
                            },
                            timeout=120)
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def pages(session: requests.Session, text: str, variables: dict,
          keys: tuple[str, ...]) -> list[dict]:
    """Follow every source cursor, without a task-specific row limit."""
    cursor = None
    seen = set()
    rows = []
    while True:
        value = query(session, text, {**variables, "cursor": cursor})
        for key in keys:
            value = value[key]
        rows.extend(edge["node"] for edge in value["edges"])
        if not value["pageInfo"]["hasNextPage"]:
            return rows
        cursor = value["pageInfo"]["endCursor"]
        if not cursor or cursor in seen:
            raise RuntimeError("W&B pagination did not advance")
        seen.add(cursor)


def capture(entity: str, project: str, destination: Path) -> Path:
    """Freeze full runs, history and original file bytes for one project."""
    variables = {"entity": entity, "project": project}
    with requests.Session() as session:
        session.trust_env = False
        metadata = query(session, PROJECT, variables)["project"]
        runs = pages(session, RUNS, variables, ("project", "runs"))
        if len(runs) != metadata["runCount"]:
            raise RuntimeError("W&B run inventory changed during capture")
        for run in runs:
            at = {**variables, "run": run["name"]}
            for key in ("config", "summaryMetrics", "systemMetrics"):
                if isinstance(run[key], str):
                    run[key] = json.loads(run[key])
            if run["sweepName"]:
                raise RuntimeError("Capture the referenced sweep before use")
            history = []
            last = run["historyKeys"]["lastStep"]
            for start in range(0, last + 1, 100):
                stop = min(start + 100, last + 1)
                # W&B's legacy endpoint can omit a one-step window.
                data = query(
                    session, HISTORY, {
                        **at,
                        "start":
                        max(0, start - 1) if stop - start == 1 else start,
                        "stop": max(stop, 2),
                        "samples": 100,
                    })["project"]["run"]["history"]
                history.extend(
                    row for raw in data
                    if start <= (row := json.loads(raw))["_step"] < stop)
            if len(history) != run["historyLineCount"]:
                raise RuntimeError(f"Incomplete history: {run['name']}")
            if len({row["_step"] for row in history}) != len(history):
                raise RuntimeError("Duplicate captured history steps")
            run["history"] = history
            run["historySamples"] = []
            for args in ({}, {"samples": 500}, {"samples": 1000}):
                arguments = "" if not args else f"(samples:{args['samples']})"
                sampled = query(
                    session, """query($entity:String!,$project:String!,
                  $run:String!) { project(entityName:$entity,name:$project) {
                  run(name:$run) { history""" + arguments + "} } }", at)
                run["historySamples"].append({
                    "args":
                    args,
                    "rows":
                    sampled["project"]["run"]["history"],
                })
            files = pages(session, FILES, at, ("project", "run", "files"))
            # The live count includes files absent from the public connection.
            # Exhaust its cursors and preserve both observations.
            run["capturedFileCount"] = len(files)
            run["files"] = {}
            for file in files:
                response = session.get(file["directUrl"], timeout=120)
                response.raise_for_status()
                content = response.content
                digest = base64.b64encode(
                    hashlib.md5(content).digest()).decode()
                if file["md5"] is not None and digest != file["md5"]:
                    raise RuntimeError(
                        f"File changed during capture: {file['name']}")
                run["files"][file["name"]] = {
                    "sourceId": file["id"],
                    "base64": base64.b64encode(content).decode(),
                    "mimetype": file["mimetype"],
                    "updatedAt": file["updatedAt"],
                    "sourceSizeBytes": file["sizeBytes"],
                    "sourceMd5": file["md5"],
                }
            print(
                f"{entity}/{project}/{run['name']}: "
                f"{len(history)} history rows, {len(files)} files",
                flush=True)
    # Authentication identity belongs to the local mock, never to the person
    # capturing it. No real key, netrc or account response is read or stored.
    fixture = {
        "source": {
            "url": f"https://wandb.ai/{entity}/{project}",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "queries": {
                "project": PROJECT,
                "runs": RUNS,
                "history": HISTORY,
                "files": FILES
            }
        },
        "entities": {
            entity: {
                project: runs
            }
        },
        "projects": {
            f"{entity}/{project}": {
                **metadata, "sweeps": {}
            }
        },
        "viewer": {
            "id": "fixture",
            "name": "fixture",
            "username": "fixture",
            "entity": entity,
            "email": None,
            "admin": False,
            "flags": "{}",
            "teams": {
                "edges": [{
                    "node": {
                        "name": entity
                    }
                }]
            }
        },
    }
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{project}.json"
    path.write_text(
        json.dumps(fixture, ensure_ascii=False, separators=(",", ":")) + "\n")
    return path


def capture_selected(path: Path) -> None:
    """Capture task-metric downsampling; never invent a sampling algorithm."""
    fixture = json.loads(path.read_text())
    query_text = """query($entity:String!,$project:String!,$run:String!,
      $specs:[JSONString!]!) {project(entityName:$entity,name:$project) {
      run(name:$run) {sampledHistory(specs:$specs)}}}"""
    metrics = [
        "actor/entropy_loss", "response_length/clip_ratio",
        "response_length/mean"
    ]
    groups = [["val/test_score/"], *[
        list(keys) for size in range(1,
                                     len(metrics) + 1)
        for keys in combinations(metrics, size)
    ]]
    groups += [["_step", *keys] for keys in groups.copy()]
    with requests.Session() as session:
        session.trust_env = False
        for entity, projects in fixture["entities"].items():
            for project, runs in projects.items():
                for run in runs:
                    specs = [{
                        "keys": keys,
                        "samples": samples
                    } for keys in groups for samples in (*range(1, 21), 50,
                                                         100, 200, 500, 1000)]
                    specs += [{}, {"samples": 500}]
                    specs += [{"keys": keys} for keys in groups]
                    specs += [{
                        "keys": ["_step", "val/test_score/"],
                        "samples": 500,
                        "minStep": 20,
                        "maxStep": 30
                    }]
                    # Verify accepted legacy options before ignoring them.
                    option_specs = [{
                        "keys": ["_step", *metrics],
                        "samples": samples,
                        **extra
                    } for samples in (5, 1000) for extra in ({
                        "x_axis": "_step"
                    }, {
                        "start": 0,
                        "end": 499
                    }, {
                        "stride": 100
                    })]
                    specs += option_specs
                    data = query(
                        session, query_text, {
                            "entity": entity,
                            "project": project,
                            "run": run["name"],
                            "specs": [json.dumps(spec) for spec in specs],
                        })["project"]["run"]["sampledHistory"]
                    run["selectedHistorySamples"] = [{
                        "spec": spec,
                        "rows": rows
                    } for spec, rows in zip(specs, data, strict=True)]
                    for spec in option_specs:
                        baseline = {
                            "keys": spec["keys"],
                            "samples": spec["samples"]
                        }
                        if data[specs.index(spec)] != data[specs.index(
                                baseline)]:
                            raise RuntimeError("W&B history option changed")
                    count = len(specs)
                    print(f"{run['name']}: {count} selected-history captures",
                          flush=True)
    fixture["source"]["queries"]["sampledHistory"] = query_text
    fixture["source"]["selected_captured_at"] = datetime.now(
        timezone.utc).isoformat()
    path.write_text(
        json.dumps(fixture, ensure_ascii=False, separators=(",", ":")) + "\n")


def capture_windows(path: Path) -> None:
    """Keep source responses for the legacy API's irregular one-step reads."""
    fixture = json.loads(path.read_text())
    with requests.Session() as session:
        session.trust_env = False
        for entity, projects in fixture["entities"].items():
            for project, runs in projects.items():
                for run in runs:
                    last = run["historyKeys"]["lastStep"]
                    steps = sorted({*range(0, last + 1, 100), last})
                    args = [{
                        "minStep": step,
                        "maxStep": step + 1,
                        **({
                            "samples": samples
                        } if samples else {})
                    } for step in steps for samples in (None, 1, 5, 500, 1000)]
                    fields = " ".join(
                        f"h{i}:history(" +
                        ",".join(f"{key}:{value}"
                                 for key, value in item.items()) + ")"
                        for i, item in enumerate(args))
                    text = ("query($entity:String!,$project:String!,"
                            "$run:String!){project(entityName:$entity,"
                            "name:$project){run(name:$run){" + fields + "}}}")
                    data = query(session, text, {
                        "entity": entity,
                        "project": project,
                        "run": run["name"]
                    })["project"]["run"]
                    run["historySamples"] = [
                        item for item in run["historySamples"]
                        if "minStep" not in item["args"]
                    ] + [{
                        "args": item,
                        "rows": data[f"h{i}"]
                    } for i, item in enumerate(args)]
                    print(f"{run['name']}: {len(args)} one-step captures",
                          flush=True)
    fixture["source"]["windows_captured_at"] = datetime.now(
        timezone.utc).isoformat()
    path.write_text(
        json.dumps(fixture, ensure_ascii=False, separators=(",", ":")) + "\n")


def check_snapshot(fixture: dict) -> None:
    """Reject run/project changes during a multi-request capture."""
    with requests.Session() as session:
        session.trust_env = False
        for entity, projects in fixture["entities"].items():
            for project, runs in projects.items():
                at = {"entity": entity, "project": project}
                metadata = query(session, PROJECT, at)["project"]
                expected = fixture["projects"][f"{entity}/{project}"]
                if metadata != {key: expected[key] for key in metadata}:
                    raise RuntimeError("W&B project changed during capture")
                latest = pages(session, RUNS, at, ("project", "runs"))
                before = {run["name"]: run for run in runs}
                if set(before) != {run["name"] for run in latest}:
                    raise RuntimeError("W&B run inventory changed")
                for run in latest:
                    for key in ("config", "summaryMetrics", "systemMetrics"):
                        if isinstance(run[key], str):
                            run[key] = json.loads(run[key])
                    if run != {key: before[run["name"]][key] for key in run}:
                        raise RuntimeError("W&B run changed during capture")


def main() -> None:
    """Publish a complete capture atomically, preserving a failed refresh."""
    upstream = REPO / "submodule/Toolathlon"
    revision = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    tasks = ("wandb-best-score", "wandb-shortest-length")
    source_tasks = {}
    for task in tasks:
        path = f"tasks/finalpool/{task}/docs/task.md"
        content = subprocess.check_output(
            ["git", "-C", str(upstream), "show", f"HEAD:{path}"])
        if b"https://wandb.ai/mluo/deepscaler-1.5b" not in content:
            raise RuntimeError("Upstream W&B project changed; review capture")
        source_tasks[path] = hashlib.sha256(content).hexdigest()
    DEST.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=DEST) as scratch:
        captured = capture("mluo", "deepscaler-1.5b", Path(scratch))
        capture_selected(captured)
        capture_windows(captured)
        fixture = json.loads(captured.read_text())
        check_snapshot(fixture)
        fixture["source"]["toolathlon"] = {
            "revision": revision,
            "task_sha256": source_tasks
        }
        fixture["source"]["capture_sha256"] = {
            str(path.relative_to(REPO)):
            hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__).resolve(), REPO / "uv.lock")
        }
        captured.write_text(
            json.dumps(fixture, ensure_ascii=False, separators=(",", ":")) +
            "\n")
        target = DEST / captured.name
        captured.replace(target)
    print(target)


if __name__ == "__main__":
    main()
