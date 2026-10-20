"""Exercise the real MCP/VFS surfaces and unchanged Toolathlon graders."""
import csv
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
for directory in ("agent", "task", "server/mcp", "tests"):
    sys.path.insert(0, str(REPO / directory))

import arms  # noqa: E402
import dataset  # noqa: E402
import parity  # noqa: E402
import toolathlon  # noqa: E402
from workspace import Workspace, config_for  # noqa: E402

TASKS = ("wandb-best-score", "wandb-shortest-length")
FIXTURE = REPO / "task/toolathlon/shared/fixtures/wandb/deepscaler-1.5b.json"


def evaluator(task):
    """Import the original grader, without editing its source."""
    spec = importlib.util.spec_from_file_location(task,
                                                  toolathlon.evaluator(task))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def answers(runs):
    """Solve from observations, without reading the task's answer key."""
    candidates = [(row["val/test_score/"], row["_step"], run["displayName"])
                  for run in runs for row in run["history"]
                  if isinstance(row.get("val/test_score/"), (int, float))]
    score, step, name = max(candidates)
    best = [{
        "best_experiment_name": name,
        "best_step": step,
        "best_val_score": score
    }]

    def average(run):
        values = [
            row["response_length/mean"] for row in run["history"]
            if isinstance(row.get("response_length/mean"), (int, float))
        ]
        return sum(values) / len(values)

    shortest = min(runs, key=average)
    rows = [{
        "step": row["_step"],
        "entropy_loss": row["actor/entropy_loss"],
        "clip_ratio": row["response_length/clip_ratio"],
        "response_length_mean": row["response_length/mean"]
    } for row in shortest["history"] if row["_step"] % 100 == 0]
    return best, rows


class WandbTasks(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        dataset.use("toolathlon")

    def test_lineage_and_initial_workspaces(self):
        for task in TASKS:
            with self.subTest(
                    task=task), tempfile.TemporaryDirectory() as work:
                source = subprocess.check_output([
                    "git", "-C",
                    str(toolathlon.root()), "show",
                    f"HEAD:tasks/finalpool/{task}/docs/task.md"
                ])
                self.assertEqual(
                    (toolathlon.local(task) / "shared/task.md").read_bytes(),
                    source)
                with patch.dict(os.environ, AGENT_WORKSPACE=work):
                    arms.build_workspace_dir(toolathlon.local(task))
                expected = {
                    p.name: p.read_bytes()
                    for p in toolathlon.initial_workspace(task).iterdir()
                }
                self.assertEqual(
                    {p.name: p.read_bytes()
                     for p in Path(work).iterdir()}, expected)
                self.assertFalse(toolathlon.needs_stack(task))

    async def test_mcp_and_vfs_answers_pass_original_graders(self):
        task = toolathlon.local(TASKS[0])
        fixture = json.loads(FIXTURE.read_text())
        capture = fixture["entities"]["mluo"]["deepscaler-1.5b"]
        previous = {
            k: os.environ.get(k)
            for k in ("WANDB_BASE_URL", "WANDB_API_KEY")
        }
        with tempfile.TemporaryDirectory() as scratch, patch.dict(
                os.environ, AGENT_WORKSPACE=scratch):
            work = arms.mirage_env(task)
            async with AsyncExitStack() as stack:
                arms.open_services(task, work, stack)
                port = int(os.environ["WANDB_BASE_URL"].rsplit(":", 1)[1])
                session = await parity.open_session(stack, "wandb", task)
                tools = await session.list_tools()
                self.assertEqual(
                    {tool.name
                     for tool in tools.tools}, {
                         "query_weave_traces_tool", "count_weave_traces_tool",
                         "query_wandb_tool", "create_wandb_report_tool",
                         "query_wandb_entity_projects",
                         "query_wandb_support_bot"
                     })
                query = '''query {
                  project(entityName:"mluo",name:"deepscaler-1.5b") {
                  id internalId isBenchmark user {id name username email}
                  runs(first:100) {edges {node {
                    id projectId name displayName history(samples:2000)
                    files(first:100) {edges {node {id name sizeBytes md5}}}}}
                  pageInfo {hasNextPage endCursor}}}}'''
                reply = json.loads(await parity.mcp_reply(
                    session, {
                        "mcp": {
                            "tool": "query_wandb_tool",
                            "args": {
                                "query": query
                            }
                        }
                    }))
                mcp_runs = [
                    edge["node"] for edge in reply["project"]["runs"]["edges"]
                ]
                for key in ("id", "internalId", "isBenchmark", "user"):
                    self.assertEqual(
                        reply["project"][key],
                        fixture["projects"]["mluo/deepscaler-1.5b"][key])
                self.assertEqual(len(mcp_runs), len(capture))
                self.assertEqual([run["name"] for run in mcp_runs], [
                    "owwdhljy", "iklki6k0", "2h1sn79d", "rq8r5vf8", "wgq08gza"
                ])
                for run in mcp_runs:
                    original = next(r for r in capture
                                    if r["name"] == run["name"])
                    self.assertEqual(run["projectId"], original["projectId"])
                    files = [edge["node"] for edge in run["files"]["edges"]]
                    self.assertEqual(
                        files, [{
                            "id": file["sourceId"],
                            "name": name,
                            "sizeBytes": file["sourceSizeBytes"],
                            "md5": file["sourceMd5"]
                        } for name, file in original["files"].items()])
                    run["history"] = [
                        json.loads(row) for row in run["history"]
                    ]
                ws = Workspace.create(config_for(task))
                stack.callback(ws.close)
                vfs_runs = []
                for run in capture:
                    base = f"/wandb/mluo/deepscaler-1.5b/{run['name']}"
                    metadata = json.loads(ws.execute(f"cat {base}/run.json"))
                    history = [
                        json.loads(line) for line in ws.execute(
                            f"cat {base}/history.jsonl").splitlines()
                    ]
                    vfs_runs.append({
                        "displayName": metadata["display_name"],
                        "history": history
                    })
                    # Default sampling is an actual source observation. A fake
                    # returning the first 500 rows would fail this assertion.
                    sampled_query = f'''query(
                        $samples:Int,$min:Int64,$max:Int64) {{
                        project(entityName:"mluo",name:"deepscaler-1.5b") {{
                        run(name:"{run['name']}") {{history
                          nullSamples:history(samples:$samples)
                          nullBounds:history(minStep:$min,maxStep:$max)
                        }}}}}}'''
                    sampled = json.loads(await parity.mcp_reply(
                        session, {
                            "mcp": {
                                "tool": "query_wandb_tool",
                                "args": {
                                    "query": sampled_query,
                                    "variables": {
                                        "samples": None,
                                        "min": None,
                                        "max": None
                                    }
                                }
                            }
                        }))
                    expected = next(item["rows"]
                                    for item in run["historySamples"]
                                    if not item["args"])
                    self.assertEqual(sampled["project"]["run"]["history"],
                                     expected)
                    self.assertEqual(sampled["project"]["run"]["nullSamples"],
                                     expected)
                    self.assertEqual(sampled["project"]["run"]["nullBounds"],
                                     expected)
                    windows = [
                        item for item in run["historySamples"]
                        if "minStep" in item["args"]
                    ]
                    fields = " ".join(f"h{i}:history(" + ",".join(
                        f"{key}:{value}"
                        for key, value in reversed(item["args"].items())) + ")"
                                      for i, item in enumerate(windows))
                    window_query = ('query {project(entityName:"mluo",'
                                    'name:"deepscaler-1.5b"){run(name:"' +
                                    run["name"] + '"){' + fields + '}}}')
                    window_reply = json.loads(await parity.mcp_reply(
                        session, {
                            "mcp": {
                                "tool": "query_wandb_tool",
                                "args": {
                                    "query": window_query
                                }
                            }
                        }))
                    self.assertEqual(window_reply["project"]["run"], {
                        f"h{i}": item["rows"]
                        for i, item in enumerate(windows)
                    })
                    selected_query = '''query($run:String!,
                        $specs:[JSONString!]!) {
                        project(entityName:"mluo",name:"deepscaler-1.5b") {
                        run(name:$run) {sampledHistory(specs:$specs)}}}'''
                    observations = run["selectedHistorySamples"]
                    specs = [item["spec"] for item in observations]
                    specs.append({
                        "keys": ["_step", "val/test_score/"],
                        "samples": 2000
                    })
                    expected = [item["rows"] for item in observations]
                    expected.append(
                        next(item["rows"] for item in observations
                             if item["spec"] == {
                                 "keys": ["_step", "val/test_score/"],
                                 "samples": 1000
                             }))
                    selected = json.loads(await parity.mcp_reply(
                        session, {
                            "mcp": {
                                "tool": "query_wandb_tool",
                                "args": {
                                    "query": selected_query,
                                    "variables": {
                                        "run":
                                        run["name"],
                                        "specs":
                                        [json.dumps(spec) for spec in specs]
                                    }
                                }
                            }
                        }))
                    self.assertEqual(
                        selected["project"]["run"]["sampledHistory"], expected)
                self.assertEqual(answers(mcp_runs), answers(vfs_runs))
                for arm, runs in (("mcp", mcp_runs), ("vfs", vfs_runs)):
                    best, shortest = answers(runs)
                    for task_name, rows in zip(TASKS, (best, shortest)):
                        with self.subTest(arm=arm, task=task_name):
                            path = Path(scratch) / f"{arm}-{task_name}.csv"
                            with path.open("w", newline="") as file:
                                writer = csv.DictWriter(file,
                                                        fieldnames=list(
                                                            rows[0]))
                                writer.writeheader()
                                writer.writerows(rows)
                            grade = evaluator(task_name)
                            if task_name == TASKS[0]:
                                result = grade._check_best_experiment(
                                    str(path))
                            else:
                                truth = toolathlon.task_dir(
                                    task_name).joinpath(
                                        "groundtruth_workspace",
                                        "shortest_length_experiment.csv")
                                result = grade._check_shortest_length(
                                    str(path), str(truth))
                            self.assertTrue(result[0], result[1])
        self.assertEqual({k: os.environ.get(k) for k in previous}, previous)
        with self.assertRaises(OSError):
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                self.fail("W&B fixture survived the arm's cleanup")


if __name__ == "__main__":
    unittest.main()
