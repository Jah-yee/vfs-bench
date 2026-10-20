"""Regression checks for Toolathlon issue #7, without models or services."""
import asyncio
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
for directory in ("", "agent", "cli", "server/clients", "server/seed", "task"):
    sys.path.insert(0, str(REPO / directory))

import arms  # noqa: E402
import dataset  # noqa: E402
import toolathlon  # noqa: E402


class Fidelity(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        dataset.use("toolathlon")

    def test_parallel_settings(self):
        source = subprocess.check_output([
            "git", "-C",
            str(toolathlon.root()), "show", "HEAD:scripts/run_parallel.sh"
        ],
                                         text=True)
        import re
        for name, upstream in (("MAX_TURNS", "MAX_STEPS"),
                               ("MAX_TOKENS", "MAX_TOKENS"), ("TIMEOUT",
                                                              "TIMEOUT")):
            value = int(
                re.search(rf'^{upstream}="(\d+)"', source, re.MULTILINE)[1])
            self.assertEqual(getattr(dataset, name), value)
        self.assertTrue(dataset.PARALLEL_TOOL_CALLS)

    def test_both_prompts_use_upstream_single_turn_and_clock(self):
        SystemPrompts = toolathlon.system_prompts_type()
        from datetime import datetime
        task = toolathlon.local("course-assistant")
        source = dataset.prompt(task.name).read_text()
        time = "2026-09-16 12:00:00"
        stamp = datetime.fromisoformat(time).strftime("%Y-%m-%d %H:%M:%S %A")
        expected = SystemPrompts(agent=source,
                                 user=None).apply("/work",
                                                  "",
                                                  stamp,
                                                  single_turn_mode=True).agent
        with patch("grading.seeded_at", return_value=time):
            actual = toolathlon.apply_system_prompt(source, task.name, "/work")
            shell = arms.build_shell_prompt(task)
        self.assertEqual(actual, expected)
        suffix = SystemPrompts(agent="",
                               user=None).apply("/work",
                                                "",
                                                stamp,
                                                single_turn_mode=True).agent
        self.assertTrue(shell.endswith(suffix))
        # Upstream's way to finish, with the shell as the one tool.
        self.assertIn(
            "If you believe the task is completed, respond without calling "
            "the `shell` tool to indicate completion.", shell)
        self.assertNotIn("claim_done", shell)
        self.assertIn(stamp, shell)
        self.assertNotIn("!!<<<<||||time||||>>>>!!", actual)

    def test_course_mail_matches_upstream_accounts(self):
        from email.utils import parseaddr

        import seed_mail
        import seed_task
        task = toolathlon.task_dir("course-assistant")
        fixture = seed_task.mail_fixture("course-assistant")
        self.assertEqual(fixture, task / "files/emails.jsonl")
        accounts = json.loads((task / "emails_all_config.json").read_text())
        expected = {a["email"] for a in accounts} - {"virginia_diaz@mcp.com"}
        entries = seed_mail.entries_of(fixture)
        self.assertEqual(len(entries), 12)
        self.assertTrue({parseaddr(e["from_addr"])[1]
                         for e in entries} <= expected)
        self.assertIn("diaza48@mcp.com", expected)
        for entry in entries:
            message, folder = seed_mail.build(entry, "virginia_diaz@mcp.com")
            self.assertEqual(
                parseaddr(message["From"])[1],
                parseaddr(entry["from_addr"])[1])
            self.assertEqual(message["To"], "virginia_diaz@mcp.com")
            self.assertEqual(folder, "INBOX")
            self.assertNotIn("<<<<||||", entry["content"])

    def test_restricted_linux_uses_pinned_ip_enforcement(self):
        from server import execution
        with tempfile.TemporaryDirectory() as work, patch.object(
                execution.sys, "platform",
                "linux"), patch("server.linux_sandbox.executable",
                                return_value="/pin/sandlock"):
            command = execution.prefix(work)
            self.assertEqual(command[:2], ["/pin/sandlock", "run"])
            self.assertIn("127.0.0.0/8:*", command)
            self.assertIn("[::1]:*", command)
            self.assertNotIn("--allow-degraded", command)
            with patch("server.linux_sandbox.executable",
                       side_effect=RuntimeError(
                           "changed pinned sandbox")), self.assertRaisesRegex(
                               RuntimeError, "changed pinned sandbox"):
                execution.prefix(work)

    def test_hub_ranking_is_captured_and_not_disclosed(self):
        import yaml
        task = toolathlon.local("verl-dataset")
        snapshot = json.loads((task / "shared/search.json").read_text())
        rows = [row for page in snapshot["pages"] for row in page["body"]]
        self.assertGreater(len(rows), 20)
        self.assertGreater(len({row["downloads"] for row in rows}), 1)
        winner = max(rows, key=lambda row: row["downloads"])["id"]
        self.assertEqual(winner, "agentica-org/DeepScaleR-Preview-Dataset")
        config = yaml.safe_load((task / "vfs/workspace.yaml").read_text())
        self.assertNotIn("/hub/DeepScaleR-Preview-Dataset", config["mounts"])
        for name in ("VFS.md", "SKILL.md"):
            self.assertNotIn(winner, (task / "vfs" / name).read_text())
        self.assertIn("huggingface", config["clis"])
        self.assertIn("hf", config["clis"])

    def test_archive_preprocessed(self):
        task = toolathlon.local("apply-phd-email")
        archive = toolathlon.initial_workspace(task.name) / "files.tar.gz"
        with tarfile.open(archive) as source:
            expected = {
                str(Path(member.name)): source.extractfile(member).read()
                for member in source.getmembers() if member.isfile()
            }
        with tempfile.TemporaryDirectory() as scratch:
            with patch.dict(os.environ, AGENT_WORKSPACE=scratch):
                workspace = Path(arms.build_workspace_dir(task))
                actual = {
                    str(p.relative_to(workspace)): p.read_bytes()
                    for p in workspace.rglob("*") if p.is_file()
                }
                self.assertEqual(actual, expected)

    def test_script_managed_archive_stays_consumed(self):
        task = toolathlon.local("git-bug-hunt")
        initial = toolathlon.initial_workspace(task.name)
        with tarfile.open(initial / "files.tar.gz") as archive:
            expected = {
                str(Path(member.name))
                for member in archive.getmembers() if member.isfile()
            }
        expected.add("template.txt")
        script = task / "shared" / "seed_mock.py"
        spec = importlib.util.spec_from_file_location("git_bug_hunt_seed",
                                                      script)
        seed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed)

        for arm in ("mcp", "vfs"):
            with self.subTest(arm=arm), tempfile.TemporaryDirectory(
            ) as scratch, patch.dict(os.environ,
                                     AGENT_WORKSPACE=scratch), patch.object(
                                         seed, "reset_mail"):
                seed.main()
                workspace = Path(arms.build_workspace_dir(task))
                self.assertFalse((workspace / "files.tar.gz").exists())
                self.assertTrue((workspace / "LUFFY" / ".git").is_dir())
                self.assertEqual(
                    {
                        str(path.relative_to(workspace))
                        for path in workspace.rglob("*") if path.is_file()
                    }, expected)
                self.assertEqual((workspace / "template.txt").read_bytes(),
                                 (initial / "template.txt").read_bytes())

    async def test_overlapping_airgaps_restore_after_last_exit(self):
        entered = [asyncio.Event(), asyncio.Event()]
        release = [asyncio.Event(), asyncio.Event()]

        async def call(index):
            with arms.fixture_network():
                entered[index].set()
                await release[index].wait()

        for first in (0, 1):
            with self.subTest(first=first):
                for event in entered + release:
                    event.clear()
                before = {k: os.environ.get(k) for k in arms.NO_NETWORK}
                calls = [asyncio.create_task(call(i)) for i in (0, 1)]
                await asyncio.gather(*(event.wait() for event in entered))
                release[first].set()
                await calls[first]
                self.assertEqual(
                    {k: os.environ.get(k)
                     for k in arms.NO_NETWORK}, arms.NO_NETWORK)
                calls[1 - first].cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await calls[1 - first]
                self.assertEqual(
                    {k: os.environ.get(k)
                     for k in arms.NO_NETWORK}, before)

    def test_a_hung_original_server_is_taken_down_with_the_run(self):
        """A server that never answers `initialize` still gets closed.

        The client kinds are served on a thread of this process, and the
        stop event that ends them is only read once they are serving. A
        server that hangs before that would keep the thread and, worse,
        the process it launched -- which a later run would then find
        holding the fixture it wants.
        """
        import time

        from travel_video import client_thread

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            record = work / "pid"
            params = {
                "command": "/bin/sh",
                "args": ["-c", f"echo $$ > {record}; exec sleep 600"],
                "cwd": str(work),
                "env": dict(os.environ),
            }
            with (work / "log").open("w") as log:
                thread, close = client_thread("notion", work / "endpoint",
                                              params, log)
                for _ in range(100):
                    if record.is_file() and record.read_text().strip():
                        break
                    time.sleep(0.1)
                else:
                    self.fail("the stand-in server never started")
                child = int(record.read_text())
                self.assertFalse((work / "endpoint").exists(),
                                 "a hung server published an endpoint")
                started = time.monotonic()
                close()
                self.assertLess(time.monotonic() - started, 25,
                                "closing a hung server did not return")
                self.assertFalse(thread.is_alive(), "the thread outlived it")
                for _ in range(100):
                    try:
                        os.kill(child, 0)
                    except (ProcessLookupError, PermissionError):
                        break
                    time.sleep(0.1)
                else:
                    self.fail(f"the server at pid {child} outlived the run")

    def test_airgap_exception_restores_existing_proxy(self):
        with patch.dict(os.environ, HTTP_PROXY="http://original.invalid"):
            before = {k: os.environ.get(k) for k in arms.NO_NETWORK}
            with self.assertRaises(RuntimeError):
                with arms.fixture_network():
                    raise RuntimeError("tool failed")
            self.assertEqual({k: os.environ.get(k)
                              for k in arms.NO_NETWORK}, before)

    def test_mirage_http_reaches_the_public_network_where_mcp_does(self):
        """Mirage's curl and wget follow the MCP arm's own model tools.

        nvidia-market's `curl` to sec.gov must not be refused where the
        MCP arm's terminal in upstream's image downloads the same files. A task with no terminal or `python_execute`, a
        Kubernetes task and an E2B one keep the loopback-only hook.
        """
        import workspace
        tasks = REPO / "task" / "toolathlon"
        expected = {
            "nvidia-market": True,
            "nvidia-stock-analysis": True,
            "sales-accounting": True,
            "woocommerce-product-recall": False,
            "trip-adviser": False,
            "k8s-redis-helm-upgrade": False,
        }
        with patch("server.shared_workspace.active", return_value=None):
            for task, public in expected.items():
                with self.subTest(task=task):
                    self.assertEqual(arms.public_network(tasks / task), public)
        with patch("server.shared_workspace.active", return_value=object()):
            self.assertFalse(arms.public_network(tasks / "nvidia-market"))
        hook = str(REPO / "cli" / "fixture-network.mjs")
        self.assertEqual(workspace.network_hook(True), [])
        self.assertEqual(workspace.network_hook(False), ["--import", hook])

    def test_pdf_serializer_matches_upstream_groundtruth(self):
        # Import the exact mounted wheel, not a host-installed PDF library.
        lock = tomllib.loads(
            (REPO / "vendor/pdf-tools-mcp/uv.lock").read_text())
        version = next(p["version"] for p in lock["package"]
                       if p["name"] == "pypdf2")
        wheel = REPO / "vendor/wheels" / f"pypdf2-{version}-py3-none-any.whl"
        with patch.object(sys, "path", [str(wheel), *sys.path]):
            import PyPDF2
        task = toolathlon.task_dir("apply-phd-email")
        names = ("Outstanding_Student_Award_2021.pdf",
                 "Research_Competition_First_Place_2022.pdf",
                 "Academic_Excellence_Award_2023.pdf")
        writer = PyPDF2.PdfWriter()
        with tarfile.open(task / "initial_workspace/files.tar.gz") as archive:
            for name in names:
                content = archive.extractfile("./Application_Materials_flat/" +
                                              name).read()
                for page in PyPDF2.PdfReader(io.BytesIO(content)).pages:
                    writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
        with tarfile.open(task /
                          "groundtruth_workspace/files.tar.gz") as archive:
            name = next(n for n in archive.getnames()
                        if n.endswith("All_Awards_Certificates.pdf"))
            expected = archive.extractfile(name).read()
        self.assertEqual(output.getvalue(), expected)


if __name__ == "__main__":
    unittest.main()
