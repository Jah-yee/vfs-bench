"""Verify the original Toolathlon filesystem and Excel MCP surfaces."""
# flake8: noqa: E402
import importlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

REPO = Path(__file__).resolve().parents[1]
for directory in ("agent", "task"):
    sys.path.insert(0, str(REPO / directory))
sys.path.insert(0, str(REPO))

import dataset  # noqa: E402
import toolathlon  # noqa: E402

from server import execution, shared_workspace  # noqa: E402
from server.mcp import mcp_servers  # noqa: E402
from server.mcp.setup_filesystem import PACKAGE  # noqa: E402
from server.mcp.setup_filesystem import VERSION  # noqa: E402
from server.mcp.setup_filesystem import (ENTRY, dependency_fingerprint,
                                         install_is_current,
                                         installed_tree_complete,
                                         installed_version, verify_source)
from setup.setup import STEPS, install_toolathlon_filesystem

FILESYSTEM_TOOLS = [
    "read_file",
    "read_multiple_files",
    "write_file",
    "edit_file",
    "create_directory",
    "list_directory",
    "list_directory_with_sizes",
    "directory_tree",
    "move_file",
    "search_files",
    "get_file_info",
    "list_allowed_directories",
]
EXCEL_TOOLS = [
    "apply_formula",
    "validate_formula_syntax",
    "format_range",
    "read_data_from_excel",
    "write_data_to_excel",
    "create_workbook",
    "create_worksheet",
    "create_chart",
    "create_pivot_table",
    "create_table",
    "copy_worksheet",
    "delete_worksheet",
    "rename_worksheet",
    "get_workbook_metadata",
    "merge_cells",
    "unmerge_cells",
    "copy_range",
    "delete_range",
    "validate_excel_range",
    "get_data_validation_info",
]
GYM_FILESYSTEM_TOOLS = [
    "read_file",
    "read_text_file",
    "read_media_file",
    "read_multiple_files",
    "write_file",
    "edit_file",
    "create_directory",
    "list_directory",
    "list_directory_with_sizes",
    "directory_tree",
    "move_file",
    "search_files",
    "get_file_info",
    "list_allowed_directories",
]


@asynccontextmanager
async def client_session(params: dict):
    """Start one locked stdio server and yield an initialized client."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(
            stdio_client(StdioServerParameters(**params)))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        yield session


async def tool_names(params: dict) -> list[str]:
    """Start one locked stdio server and return its advertised tool names."""
    async with client_session(params) as session:
        return [tool.name for tool in (await session.list_tools()).tools]


class OriginalMCPLineage(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        dataset.use("toolathlon")

    def test_versions_and_launchers_match_original_locks(self):
        verify_source()
        self.assertEqual(VERSION, "2025.7.1")
        self.assertEqual(installed_version(), VERSION)
        upstream_npm = json.loads(
            subprocess.check_output([
                "git", "-C",
                str(toolathlon.root()), "show", "HEAD:package-lock.json"
            ]))
        self.assertEqual(
            upstream_npm["packages"]["node_modules/" + PACKAGE]["version"],
            VERSION)

        upstream_uv = tomllib.loads(
            subprocess.check_output(
                ["git", "-C",
                 str(toolathlon.root()), "show", "HEAD:uv.lock"],
                text=True))
        excel = next(package for package in upstream_uv["package"]
                     if package["name"] == "excel-mcp-server")
        self.assertEqual(excel["version"], "0.1.4")
        installed_excel = subprocess.check_output([
            str(toolathlon.root() / ".venv/bin/python"), "-c",
            "import importlib.metadata as m;"
            "print(m.version('excel-mcp-server'))"
        ],
                                                  text=True).strip()
        self.assertEqual(installed_excel, excel["version"])

        task = toolathlon.local("course-schedule")
        with tempfile.TemporaryDirectory() as directory, patch.object(
                shared_workspace, "CURRENT", None):
            at = mcp_servers.Launch(task, directory)
            filesystem = mcp_servers.filesystem(at)
            excel_params = mcp_servers.excel(at)
        self.assertEqual(filesystem["command"], "node")
        self.assertEqual(filesystem["args"], [str(ENTRY), directory])
        self.assertEqual(excel_params["command"], "uv")
        self.assertEqual(excel_params["args"],
                         ["run", "--locked", "excel-mcp-server", "stdio"])
        self.assertEqual(excel_params["env"]["UV_PROJECT"],
                         str(toolathlon.root()))
        self.assertEqual(excel_params["cwd"], directory)
        with patch.object(execution, "prepare_project") as prepare:
            execution.prepare(excel_params)
        prepare.assert_called_once_with(str(toolathlon.root()))
        with patch.object(execution, "prefix",
                          return_value=["sandbox"]) as boundary:
            execution.launch(excel_params, directory)
        readable = boundary.call_args.args[1]
        self.assertNotIn(toolathlon.root(), readable)
        self.assertIn(toolathlon.root() / ".venv", readable)

        source_fs = yaml.safe_load(mcp_servers.upstream_config("filesystem"))
        source_excel = yaml.safe_load(mcp_servers.upstream_config("excel"))
        self.assertEqual(
            source_fs["params"], {
                "command": "npx",
                "args": ["-y", PACKAGE, "${agent_workspace}"],
                "cwd": "${agent_workspace}",
            })
        self.assertEqual(
            source_excel["params"], {
                "command": "uv",
                "args": ["run", "excel-mcp-server", "stdio"],
                "cwd": "${agent_workspace}",
            })
        original_setup = next(step for step in STEPS
                              if step[0] == "Toolathlon filesystem MCP server")
        self.assertIs(original_setup[1], install_toolathlon_filesystem)

    def test_e2b_launchers_use_the_same_locked_installations(self):

        class Remote:

            @staticmethod
            def launch(command, env=None):
                return {"remote_command": command, "remote_env": env}

        task = toolathlon.local("course-schedule")
        with patch.object(shared_workspace, "CURRENT", Remote()):
            at = mcp_servers.Launch(task, "/local/work")
            filesystem = mcp_servers.filesystem(at)
            excel = mcp_servers.excel(at)
        self.assertEqual(filesystem["remote_command"], [
            "node", "/opt/filesystem/node_modules/@modelcontextprotocol/"
            "server-filesystem/dist/index.js", "/work"
        ])
        self.assertEqual(
            excel["remote_command"],
            ["/opt/agent-python/.venv/bin/excel-mcp-server", "stdio"])
        self.assertEqual(excel["remote_env"],
                         {"PYTHONPATH": "/opt/excel-redirect"})

    async def test_locked_servers_advertise_original_tool_sets(self):
        task = toolathlon.local("course-schedule")
        with tempfile.TemporaryDirectory() as directory, patch.object(
                shared_workspace, "CURRENT", None):
            at = mcp_servers.Launch(task, directory)
            filesystem = mcp_servers.filesystem(at)
            excel = mcp_servers.excel(at)
            self.assertEqual(await tool_names(filesystem), FILESYSTEM_TOOLS)
            self.assertEqual(await tool_names(excel), EXCEL_TOOLS)

    async def test_local_launch_round_trip_stays_inside_workspace(self):
        task = toolathlon.local("course-schedule")
        with tempfile.TemporaryDirectory() as directory, \
                tempfile.TemporaryDirectory() as outside, patch.object(
                    shared_workspace, "CURRENT", None):
            work = Path(directory).resolve()
            secret = Path(outside).resolve() / "secret.txt"
            secret.write_text("host secret")
            source = work / "source.txt"
            source.write_text("inside")
            at = mcp_servers.Launch(task, str(work))

            filesystem = execution.launch(mcp_servers.filesystem(at),
                                          str(work))
            async with client_session(filesystem) as session:
                read = await session.call_tool("read_file",
                                               {"path": str(source)})
                self.assertFalse(read.isError)
                self.assertEqual(read.content[0].text, "inside")
                written = work / "written.txt"
                result = await session.call_tool("write_file", {
                    "path": str(written),
                    "content": "written inside",
                })
                self.assertFalse(result.isError)
                self.assertEqual(written.read_text(), "written inside")
                denied = await session.call_tool("read_file",
                                                 {"path": str(secret)})
                self.assertTrue(denied.isError)
                self.assertNotIn("host secret", denied.content[0].text)

            excel = mcp_servers.excel(at)
            execution.prepare(excel)
            excel = execution.launch(excel, str(work))
            workbook = work / "round-trip.xlsx"
            async with client_session(excel) as session:
                created = await session.call_tool("create_workbook",
                                                  {"filepath": str(workbook)})
                self.assertFalse(created.isError)
                write = await session.call_tool(
                    "write_data_to_excel", {
                        "filepath": str(workbook),
                        "sheet_name": "Sheet1",
                        "data": [["status", "ok"]],
                        "start_cell": "A1",
                    })
                self.assertFalse(write.isError)
                read = await session.call_tool(
                    "read_data_from_excel", {
                        "filepath": str(workbook),
                        "sheet_name": "Sheet1",
                        "start_cell": "A1",
                        "end_cell": "B1",
                    })
                self.assertFalse(read.isError)
                self.assertIn('"value": "status"', read.content[0].text)
                self.assertIn('"value": "ok"', read.content[0].text)
                outside_book = Path(outside).resolve() / "outside.xlsx"
                denied = await session.call_tool(
                    "create_workbook", {"filepath": str(outside_book)})
                self.assertFalse(denied.isError)
                self.assertTrue(denied.content[0].text.startswith("Error:"))
                self.assertFalse(outside_book.exists())

    def test_install_fingerprint_covers_the_transitive_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            installed = home / "node_modules" / PACKAGE
            entry = installed / "dist" / "index.js"
            entry.parent.mkdir(parents=True)
            entry.write_text("// fixture\n")
            (installed / "package.json").write_text(
                json.dumps({"version": VERSION}))
            transitive = home / "node_modules" / "transitive"
            transitive.mkdir()
            (transitive / "package.json").write_text(
                json.dumps({"version": "1.0.0"}))
            expected = {
                "name": "fixture",
                "lockfileVersion": 3,
                "packages": {
                    "": {
                        "dependencies": {
                            PACKAGE: VERSION
                        }
                    },
                    "node_modules/" + PACKAGE: {
                        "version": VERSION
                    },
                    "node_modules/transitive": {
                        "version": "1.0.0"
                    },
                },
            }
            actual = {
                "name": "fixture",
                "lockfileVersion": 3,
                "packages": {
                    "node_modules/" + PACKAGE: {
                        "version": VERSION
                    },
                    "node_modules/transitive": {
                        "version": "1.0.0"
                    },
                },
            }
            (home / "package-lock.json").write_text(json.dumps(expected))
            hidden = home / "node_modules" / ".package-lock.json"
            hidden.write_text(json.dumps(actual))
            self.assertEqual(
                dependency_fingerprint(home / "package-lock.json"),
                dependency_fingerprint(hidden))
            self.assertTrue(install_is_current(home, installed, entry,
                                               VERSION))
            self.assertTrue(installed_tree_complete(home))

            actual["packages"]["node_modules/transitive"]["version"] = "2.0.0"
            hidden.write_text(json.dumps(actual))
            self.assertFalse(
                install_is_current(home, installed, entry, VERSION),
                "a changed transitive lock entry must force npm ci")

            actual["packages"]["node_modules/transitive"]["version"] = "1.0.0"
            hidden.write_text(json.dumps(actual))
            (transitive / "package.json").unlink()
            transitive.rmdir()
            self.assertFalse(
                install_is_current(home, installed, entry, VERSION),
                "a missing declared transitive package must force npm ci")
            self.assertFalse(installed_tree_complete(home))

    async def test_gym_filesystem_setup_and_tool_surface(self):
        gym_root = REPO / "submodule" / "toolathlon_gym"
        gym_server = gym_root / "local_servers" / "filesystem"
        install = (
            "GYM filesystem MCP server",
            ("npm", "install", "--ignore-scripts"),
            gym_server,
        )
        self.assertIn(install, STEPS)

        gym = importlib.import_module("toolathlon-gym")
        with tempfile.TemporaryDirectory() as directory:
            params = gym.filesystem(
                SimpleNamespace(vendored=gym_root / "local_servers",
                                workdir=directory))
            source = yaml.safe_load(
                subprocess.check_output([
                    "git", "-C",
                    str(gym_root), "show",
                    "HEAD:configs/mcp_servers/filesystem.yaml"
                ]))
            self.assertEqual(source["params"]["command"], params["command"])
            self.assertEqual(source["params"]["args"], [
                "${local_servers_paths}/filesystem/dist/index.js",
                "${agent_workspace}"
            ])
            self.assertEqual(
                params["args"],
                [str(gym_server / "dist" / "index.js"), directory])
            self.assertEqual(await tool_names(params), GYM_FILESYSTEM_TOOLS)


@unittest.skipUnless(
    os.environ.get("RUN_E2B_MCP_LINEAGE") == "1",
    "set RUN_E2B_MCP_LINEAGE=1 for the paid E2B smoke")
class RemoteMCPLineage(unittest.IsolatedAsyncioTestCase):

    async def test_remote_workspace_stdio_and_cleanup(self):
        """Exercise both locked stdio servers through a real owned sandbox."""
        from server.kubernetes_template import receipt
        from server.sandbox import sandbox
        from server.shared_workspace import remote_workspace, run

        if not os.environ.get("E2B_API_KEY"):
            self.skipTest("E2B_API_KEY is required")
        dataset.use("toolathlon")
        template = receipt()
        assets = json.loads(
            (REPO / "server/kubernetes-binaries.json").read_text())
        task = toolathlon.local("course-schedule")
        box = None
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory).resolve()
            with sandbox(template["template_id"],
                         {"test": "original-mcp-lineage"}) as box:
                run(
                    box, "python3 -m pip install --break-system-packages -q "
                    "uv==0.8.22")
                run(box, "install -d -o user -g user /work")
                with remote_workspace(box, {
                        "bucket": "unused",
                        "key_prefix": "unused/work",
                },
                                      str(work),
                                      None,
                                      assets,
                                      shared_disk=True) as remote:
                    self.assertIs(shared_workspace.active(), remote)
                    remote.save("source.txt", "inside")
                    at = mcp_servers.Launch(task, str(work))
                    async with client_session(
                            mcp_servers.filesystem(at)) as session:
                        read = await session.call_tool(
                            "read_file", {"path": "/work/source.txt"})
                        self.assertFalse(read.isError)
                        self.assertEqual(read.content[0].text, "inside")
                        denied = await session.call_tool(
                            "read_file", {"path": "/etc/hostname"})
                        self.assertTrue(denied.isError)

                    async with client_session(
                            mcp_servers.excel(at)) as session:
                        created = await session.call_tool(
                            "create_workbook",
                            {"filepath": "/work/remote.xlsx"})
                        self.assertFalse(created.isError)
                        written = await session.call_tool(
                            "write_data_to_excel", {
                                "filepath": "/work/remote.xlsx",
                                "sheet_name": "Sheet1",
                                "data": [["remote", "ok"]],
                                "start_cell": "A1",
                            })
                        self.assertFalse(written.isError)
                        read = await session.call_tool(
                            "read_data_from_excel", {
                                "filepath": "/work/remote.xlsx",
                                "sheet_name": "Sheet1",
                                "start_cell": "A1",
                                "end_cell": "B1",
                            })
                        self.assertFalse(read.isError)
                        self.assertIn('"value": "remote"',
                                      read.content[0].text)
                        self.assertIn('"value": "ok"', read.content[0].text)
                self.assertIsNone(shared_workspace.active())
                self.assertTrue(box.is_running())
        self.assertIsNotNone(box)
        self.assertFalse(box.is_running())


if __name__ == "__main__":
    unittest.main()
