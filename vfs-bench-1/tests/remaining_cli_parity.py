"""Compare reused CLI replies with independently launched upstream servers."""
import json
import os
import re
import shlex
import socket
import sys
import tempfile
import unittest
from contextlib import AsyncExitStack, ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
for directory in ('agent', 'task'):
    sys.path.insert(0, str(REPO / directory))

import workspace as workspace_backend  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from mcp.shared.exceptions import McpError  # noqa: E402
from workspace import Workspace, config_for  # noqa: E402

from server.execution import launch  # noqa: E402
from server.fakes.wandb_api import serve as wandb_fixture  # noqa: E402
from server.mcp.mcp_servers import SERVERS, Launch  # noqa: E402
from server.seed.travel_video import serve_tools  # noqa: E402


@contextmanager
def task_workspace(task, work):
    """The task's own workspace on a daemon this test starts and stops.

    Service mounts are dropped: they have parity cases of their own, and
    the replies compared here come from the task's CLI alone.
    """
    config = config_for(REPO / 'task/toolathlon' / task)
    resolve = workspace_backend.resolved
    popen = workspace_backend.subprocess.Popen
    daemons = []

    def disk_only(path):
        body = resolve(path)
        body['mounts'] = {
            key: value
            for key, value in body['mounts'].items()
            if key in ('/workspace', '/tmp')
        }
        return body

    def start(*args, **kwargs):
        daemons.append(popen(*args, **kwargs))
        return daemons[-1]

    def stop():
        for daemon in daemons:
            daemon.terminate()
            daemon.wait(timeout=10)

    with ExitStack() as stack:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = str(sock.getsockname()[1])
        env = {
            key: 'http://127.0.0.1:1'
            for key in re.findall(r'\$\{(\w+)\}', config.read_text())
            if key not in os.environ
        }
        env.update(AGENT_WORKSPACE=str(work),
                   STACK_DIR=stack.enter_context(
                       tempfile.TemporaryDirectory()),
                   TOOLATHLON_PYTHON=str(REPO / 'vendor/toolathlon-python'),
                   MIRAGE_DAEMON_PORT=port)
        stack.enter_context(patch.dict(os.environ, env))
        stack.enter_context(patch.object(workspace_backend, '_RUNNING', None))
        stack.callback(stop)
        with patch.object(workspace_backend, 'resolved',
                          side_effect=disk_only), patch.object(
                              workspace_backend.subprocess,
                              'Popen',
                              side_effect=start):
            ws = Workspace.create(config)
        stack.callback(ws.close)
        yield ws


async def cli(ws, name, arguments):
    """Run one CLI command through the shell the agent drives."""
    return await ws.execute_result_async(shlex.join([name, *arguments]))


class OriginalReplies(unittest.IsolatedAsyncioTestCase):

    async def compare(self, kind, task, calls):
        with tempfile.TemporaryDirectory(
        ) as left, tempfile.TemporaryDirectory() as right:
            for directory in (left, right):
                (Path(directory) / 'memory').mkdir()
            params = launch(
                SERVERS[kind](Launch(REPO / 'task/toolathlon' / task, left)),
                left)
            async with AsyncExitStack() as stack:
                read, write = await stack.enter_async_context(
                    stdio_client(StdioServerParameters(**params)))
                session = await stack.enter_async_context(
                    ClientSession(read, write))
                await session.initialize()
                with serve_tools([kind], right,
                                 task), task_workspace(task, right) as ws:
                    tools = (await session.list_tools()).tools
                    for tool in tools:
                        result = await cli(ws, kind, [tool.name, '--help'])
                        self.assertEqual(result['exit_code'], 0, result)
                        # The CLI spells the tool's underscores as hyphens.
                        self.assertEqual(
                            json.loads(result['stdout']), {
                                **tool.model_dump(mode='json',
                                                  exclude_none=True), 'name':
                                tool.name.replace('_', '-')
                            })
                    for name, arguments in calls:
                        with self.subTest(service=kind, tool=name):
                            try:
                                expected = await session.call_tool(
                                    name, arguments)
                            except McpError as error:
                                actual = await cli(
                                    ws, kind,
                                    [name, json.dumps(arguments)])
                                self.assertEqual(actual['exit_code'], 1,
                                                 actual)
                                self.assertEqual(actual['stdout'], '')
                                self.assertEqual(
                                    str(error) + '\n', actual['stderr'])
                                continue
                            actual = await cli(
                                ws, kind, [name, json.dumps(arguments)])
                            failed = bool(expected.isError)
                            self.assertEqual(actual['exit_code'], int(failed),
                                             actual)
                            text = '\n'.join(block.text
                                             for block in expected.content)
                            # A failed call's text is the command's error.
                            self.assertEqual(
                                (actual['stdout'], actual['stderr']),
                                ('', text) if failed else (text, ''))
                    if kind == 'memory':
                        self.assertEqual(
                            (Path(left) / 'memory/memory.json').read_bytes(),
                            (Path(right) / 'memory/memory.json').read_bytes())

    async def test_memory_reads_mutations_and_empty_results(self):
        await self.compare('memory', 'canvas-do-quiz', [
            ('read_graph', {}),
            ('create_entities', {
                'entities': [{
                    'name': 'A',
                    'entityType': 'course',
                    'observations': ['first\nsecond']
                }, {
                    'name': 'B',
                    'entityType': 'exam',
                    'observations': []
                }]
            }),
            ('create_relations', {
                'relations': [{
                    'from': 'A',
                    'to': 'B',
                    'relationType': 'has'
                }]
            }),
            ('add_observations', {
                'observations': [{
                    'entityName': 'A',
                    'contents': ['extra']
                }]
            }),
            ('search_nodes', {
                'query': 'course'
            }),
            ('open_nodes', {
                'names': ['missing']
            }),
            ('delete_observations', {
                'deletions': [{
                    'entityName': 'A',
                    'observations': ['extra']
                }]
            }),
            ('delete_entities', {
                'entityNames': ['B']
            }),
            ('read_graph', {}),
            ('add_observations', {
                'observations': [{
                    'entityName': 'A'
                }]
            }),
        ])

    async def test_wandb_queries_and_error_results(self):
        with wandb_fixture(REPO / 'task/toolathlon/wandb-best-score'):
            await self.compare('wandb', 'wandb-best-score', [
                ('query_wandb_tool', {
                    'query':
                    'query { project(name:"deepscaler-1.5b", '
                    'entityName:"mluo") { name } }'
                }),
                ('query_wandb_tool', {
                    'query':
                    'query { project(name:"deepscaler-1.5b", '
                    'entityName:"mluo") { runs(first: 1) { edges { node { '
                    'name } } pageInfo { endCursor hasNextPage } } } }'
                }),
                ('query_wandb_tool', {
                    'query': 'query { field_that_does_not_exist }'
                }),
            ])


class BrowserReplies(unittest.IsolatedAsyncioTestCase):

    async def test_file_navigation_and_snapshot_results(self):
        from server.seed.browser import local_params, serve
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory).resolve()
            (work / 'index.html').write_text(
                '<!doctype html><title>Parity</title><h1>Same fixture</h1>'
                '<p>/workspace stays literal content.</p>')
            with serve('shopping-helper',
                       work), task_workspace('shopping-helper', work) as ws:
                async with AsyncExitStack() as stack:
                    read, write = await stack.enter_async_context(
                        stdio_client(
                            StdioServerParameters(**local_params(work))))
                    session = await stack.enter_async_context(
                        ClientSession(read, write))
                    await session.initialize()
                    for tool in (await session.list_tools()).tools:
                        verb = tool.name.removeprefix('browser_')
                        result = await cli(ws, 'browser', [verb, '--help'])
                        self.assertEqual(result['exit_code'], 0, result)
                        self.assertEqual(
                            json.loads(result['stdout']), {
                                **tool.model_dump(mode='json',
                                                  exclude_none=True), 'name':
                                verb.replace('_', '-')
                            })
                    for tool, native_args, virtual_args in [
                        ('navigate', {
                            'url': (work / 'index.html').as_uri()
                        }, {
                            'url': 'file:///workspace/index.html'
                        }),
                        ('snapshot', {}, {}),
                    ]:
                        expected = await session.call_tool(
                            'browser_' + tool, native_args)
                        actual = await cli(
                            ws, 'browser',
                            [tool, json.dumps(virtual_args)])
                        text = '\n'.join(
                            block.text for block in expected.content).replace(
                                str(work), '/workspace')
                        failed = bool(expected.isError)
                        self.assertEqual(actual['exit_code'], int(failed))
                        # A failed call's text is the command's error.
                        self.assertEqual((actual['stdout'], actual['stderr']),
                                         ('', text) if failed else (text, ''))


if __name__ == '__main__':
    unittest.main()
