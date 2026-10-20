import json
import sys
from pathlib import Path

import requests

# Re-reads every observation in the frozen W&B capture from the live public
# API and reports what moved. It writes nothing: a refresh is
# `capture_wandb.main`, run deliberately, and the fixture records that
# script's own hash, which is why this lives beside it rather than in it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_wandb as capture  # noqa: E402

SAMPLED = """query($entity:String!,$project:String!,$run:String!,
  $specs:[JSONString!]!) {project(entityName:$entity,name:$project) {
  run(name:$run) {sampledHistory(specs:$specs)}}}"""


def history_query(arguments):
    return ("query($entity:String!,$project:String!,$run:String!) {"
            "project(entityName:$entity,name:$project) {run(name:$run) {"
            "history" + arguments + "}}}")


def windows_query(windows):
    fields = " ".join(f"h{i}:history(" +
                      ",".join(f"{key}:{value}"
                               for key, value in item["args"].items()) + ")"
                      for i, item in enumerate(windows))
    return ("query($entity:String!,$project:String!,$run:String!){"
            "project(entityName:$entity,name:$project){run(name:$run){" +
            fields + "}}}")


def full_history(session, at, last):
    """The complete history, read the way `capture_wandb.capture` reads it."""
    rows = []
    for start in range(0, last + 1, 100):
        stop = min(start + 100, last + 1)
        data = capture.query(
            session, capture.HISTORY, {
                **at,
                "start": max(0, start - 1) if stop - start == 1 else start,
                "stop": max(stop, 2),
                "samples": 100,
            })["project"]["run"]["history"]
        rows.extend(row for raw in data
                    if start <= (row := json.loads(raw))["_step"] < stop)
    return rows


def check(path: Path) -> list[str]:
    """Every way the live service now differs from the capture at `path`."""
    fixture = json.loads(path.read_text())
    drift = []
    with requests.Session() as session:
        session.trust_env = False
        for entity, projects in fixture["entities"].items():
            for project, runs in projects.items():
                at = {"entity": entity, "project": project}
                metadata = capture.query(session, capture.PROJECT,
                                         at)["project"]
                expected = fixture["projects"][f"{entity}/{project}"]
                drift += [
                    f"project.{key}: {expected.get(key)!r} -> {value!r}"
                    for key, value in metadata.items()
                    if expected.get(key) != value
                ]
                live = {
                    run["name"]: run
                    for run in capture.pages(session, capture.RUNS, at, (
                        "project", "runs"))
                }
                if set(live) != {run["name"] for run in runs}:
                    drift.append("run inventory: "
                                 f"{sorted(run['name'] for run in runs)} -> "
                                 f"{sorted(live)}")
                for run in runs:
                    if run["name"] not in live:
                        continue
                    drift += run_drift(session, {
                        **at, "run": run["name"]
                    }, run, live[run["name"]])
    return drift


def run_drift(session, at, run, live):
    name = run["name"]
    for key in ("config", "summaryMetrics", "systemMetrics"):
        if isinstance(live[key], str):
            live[key] = json.loads(live[key])
    drift = [
        f"{name}.{key}: changed" for key, value in live.items()
        if run.get(key) != value
    ]
    history = full_history(session, at, run["historyKeys"]["lastStep"])
    if history != run["history"]:
        drift.append(f"{name}.history: {len(run['history'])} rows -> "
                     f"{len(history)} rows, or changed values")
    samples = [
        item for item in run["historySamples"] if "minStep" not in item["args"]
    ]
    for item in samples:
        arguments = ("" if not item["args"] else
                     f"(samples:{item['args']['samples']})")
        rows = capture.query(session, history_query(arguments),
                             at)["project"]["run"]["history"]
        if rows != item["rows"]:
            drift.append(f"{name}.history{arguments or '()'}: sample changed "
                         f"({len(item['rows'])} -> {len(rows)} rows)")
    windows = [
        item for item in run["historySamples"] if "minStep" in item["args"]
    ]
    data = capture.query(session, windows_query(windows), at)["project"]["run"]
    changed = sum(1 for i, item in enumerate(windows)
                  if data[f"h{i}"] != item["rows"])
    if changed:
        drift.append(f"{name}: {changed}/{len(windows)} one-step windows "
                     "changed")
    selected = run["selectedHistorySamples"]
    data = capture.query(session, SAMPLED, {
        **at, "specs": [json.dumps(item["spec"]) for item in selected]
    })["project"]["run"]["sampledHistory"]
    changed = sum(1 for got, item in zip(data, selected, strict=True)
                  if got != item["rows"])
    if changed:
        drift.append(f"{name}: {changed}/{len(selected)} selected-history "
                     "samples changed")
    print(
        f"{name}: {len(history)} rows, {len(samples)} samples, "
        f"{len(windows)} one-step windows, {len(selected)} selected specs "
        "re-read",
        flush=True)
    return drift


def main() -> int:
    drift = check(capture.DEST / "deepscaler-1.5b.json")
    for line in drift:
        print("drift:", line)
    print(f"{len(drift)} difference(s) from the live service")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
