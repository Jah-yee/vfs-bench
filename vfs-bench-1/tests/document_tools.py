"""Document CLIs use the pinned MCP tools over the same confined disk mount."""
import json
import os
import re
import shlex
import socket
import sys
import tarfile
import tempfile
import unittest
from contextlib import AsyncExitStack, ExitStack
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
for directory in ('', 'agent', 'task'):
    sys.path.insert(0, str(REPO / directory))

import yaml  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from workspace import Workspace  # noqa: E402

from server.clients.original_tools import (  # noqa: E402
    document_workspace_request, document_workspace_response)
from server.execution import launch  # noqa: E402
from server.mcp.mcp_servers import SERVERS, Launch  # noqa: E402
from server.seed.travel_video import serve_tools  # noqa: E402


class Paths(unittest.TestCase):

    def test_escape_rejected_and_content_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp).resolve() / 'work'
            work.mkdir()
            (work / 'outside').symlink_to(Path(tmp))
            for path in ('/etc/passwd', '/workspace/../secret', '../secret',
                         '/workspace/outside/secret', 'outside/secret'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    document_workspace_request(
                        'excel', {
                            'name': 'read_data_from_excel',
                            'arguments': {
                                'filepath': path
                            },
                        }, work)
            data = {
                'filepath': '/workspace/a.xlsx',
                'data': [[str(work) + '/literal']],
                'sheet_name': 'Sheet1'
            }
            mapped = document_workspace_request('excel', {
                'name': 'write_data_to_excel',
                'arguments': data,
            }, work)
            self.assertEqual(mapped['arguments']['filepath'],
                             str(work / 'a.xlsx'))
            self.assertEqual(mapped['arguments']['data'], data['data'])
            text = str(work) + '/literal'
            for kind, name in [('excel', 'read_data_from_excel'),
                               ('pdf-tools', 'read_pdf_pages'),
                               ('pdf-tools', 'search_pdf_content')]:
                result = {'content': [{'type': 'text', 'text': text}]}
                self.assertEqual(
                    document_workspace_response(kind, name, result, work),
                    result)
                self.assertEqual(result['content'][0]['text'], text)

    def test_office_paths_and_status_replies(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp).resolve()
            mapped = document_workspace_request(
                'word', {
                    'name': 'copy_document',
                    'arguments': {
                        'source_filename': '/workspace/a.docx',
                        'destination_filename': 'b.docx'
                    }
                }, work)
            self.assertEqual(
                mapped['arguments'], {
                    'source_filename': str(work / 'a.docx'),
                    'destination_filename': 'b.docx'
                })
            mapped = document_workspace_request(
                'pptx', {
                    'name': 'create_slide_from_template',
                    'arguments': {
                        'template_id': 'text_with_image',
                        'image_paths': {
                            'image': '/workspace/chart.png'
                        }
                    }
                }, work)
            self.assertEqual(mapped['arguments']['image_paths'],
                             {'image': str(work / 'chart.png')})
            # JPEG base64 starts with a slash and is not a path.
            encoded = {
                'slide_index': 0,
                'operation': 'add',
                'image_source': '/9j/4AAQSkZJRg==',
                'source_type': 'base64'
            }
            self.assertEqual(
                document_workspace_request('pptx', {
                    'name': 'manage_image',
                    'arguments': encoded
                }, work)['arguments'], encoded)
            with self.assertRaises(ValueError):
                document_workspace_request(
                    'pptx', {
                        'name': 'manage_image',
                        'arguments': {
                            **encoded, 'source_type': 'file'
                        }
                    }, work)
            status = str(work / 'a.docx')
            for kind, name, expected in [
                ('word', 'add_paragraph', '/workspace/a.docx'),
                ('word', 'get_document_text', status),
                ('pptx', 'save_presentation', '/workspace/a.docx'),
                ('pptx', 'extract_presentation_text', status),
            ]:
                with self.subTest(kind=kind, name=name):
                    result = {'content': [{'type': 'text', 'text': status}]}
                    document_workspace_response(kind, name, result, work)
                    self.assertEqual(result['content'][0]['text'], expected)


class DocumentTools(unittest.IsolatedAsyncioTestCase):

    async def test_cli_schemas_reads_writes_errors_and_sessions(self):
        task = REPO / 'task/toolathlon/arrange-workspace'
        with ExitStack() as stack:
            work = Path(stack.enter_context(
                tempfile.TemporaryDirectory())).resolve()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = str(sock.getsockname()[1])
            stack.enter_context(
                patch.dict(
                    os.environ, {
                        'AGENT_WORKSPACE': str(work),
                        'TOOLATHLON_PYTHON': str(
                            REPO / 'vendor/toolathlon-python'),
                        'MIRAGE_DAEMON_PORT': port,
                    }))
            archive = REPO / ('submodule/Toolathlon/tasks/finalpool/'
                              'arrange-workspace/initial_workspace/'
                              'initial_workspace.tar.gz')
            with tarfile.open(archive) as source:
                for name in ('cv-gboeing.pdf', 'exam.xlsx'):
                    member = next(m for m in source.getmembers()
                                  if Path(m.name).name == name)
                    (work / name).write_bytes(
                        source.extractfile(member).read())
            stack.enter_context(
                serve_tools(['pdf-tools', 'excel'], str(work),
                            'arrange-workspace'))
            ws = Workspace.create(task / 'vfs/workspace.yaml')
            stack.callback(ws.close)
            async with AsyncExitStack() as clients:
                sessions = {}
                log = stack.enter_context((work / 'test-server.log').open('w'))
                for kind in ('pdf-tools', 'excel'):
                    params = launch(SERVERS[kind](Launch(task, str(work))),
                                    str(work))
                    streams = await clients.enter_async_context(
                        stdio_client(StdioServerParameters(**params),
                                     errlog=log))
                    session = await clients.enter_async_context(
                        ClientSession(*streams))
                    await session.initialize()
                    sessions[kind] = session

                def cli(kind, name, arguments):
                    return ws.execute_result(
                        f'{kind} {name} ' + shlex.quote(json.dumps(arguments)))

                async def original(kind, name, arguments):
                    result = await sessions[kind].call_tool(name, arguments)
                    return '\n'.join(block.text for block in result.content)

                for kind, count in [('pdf-tools', 9), ('excel', 20)]:
                    tools = (await sessions[kind].list_tools()).tools
                    self.assertEqual(len(tools), count)
                    for tool in tools:
                        with self.subTest(kind=kind, tool=tool.name):
                            # The CLI spells the tool's underscores as hyphens.
                            spelled = tool.name.replace('_', '-')
                            shown = json.loads(
                                ws.execute(f'{kind} {tool.name} --help'))
                            schema = tool.model_dump(mode='json',
                                                     exclude_none=True)
                            schema['name'] = spelled
                            self.assertEqual(shown, schema)
                            self.assertIn(f'`{kind} {spelled}`',
                                          (task / 'vfs/SKILL.md').read_text())

                cases = [
                    ('pdf-tools', 'read_pdf_pages', 'pdf_file_path',
                     'cv-gboeing.pdf', {
                         'start_page': 1,
                         'end_page': 3
                     }),
                    ('pdf-tools', 'get_pdf_info', 'pdf_file_path',
                     'cv-gboeing.pdf', {}),
                    ('excel', 'get_workbook_metadata', 'filepath', 'exam.xlsx',
                     {
                         'include_ranges': True
                     }),
                    ('excel', 'read_data_from_excel', 'filepath', 'exam.xlsx',
                     {
                         'sheet_name': 'Sheet1',
                         'start_cell': 'A1',
                         'end_cell': 'C5'
                     }),
                ]
                for kind, name, key, file, args in cases:
                    with self.subTest(operation=name):
                        expected = await original(kind, name, {
                            key: str(work / file),
                            **args
                        })
                        actual = cli(kind, name, {
                            key: '/workspace/' + file,
                            **args
                        })
                        self.assertEqual(actual['exit_code'], 0)
                        self.assertEqual(actual['stdout'], expected)

                # Writes and shell moves must share the same mounted files.
                for name, args in [('create_workbook', {}),
                                   ('write_data_to_excel', {
                                       'sheet_name': 'Sheet1',
                                       'data': [['value'], [42]]
                                   })]:
                    await original('excel', name, {
                        'filepath': str(work / 'direct.xlsx'),
                        **args
                    })
                    self.assertEqual(
                        cli('excel', name, {
                            'filepath': '/workspace/cli.xlsx',
                            **args
                        })['exit_code'], 0)
                args = {
                    'sheet_name': 'Sheet1',
                    'start_cell': 'A1',
                    'end_cell': 'A2'
                }
                expected = await original('excel', 'read_data_from_excel', {
                    'filepath': str(work / 'direct.xlsx'),
                    **args
                })
                actual = cli('excel', 'read_data_from_excel', {
                    'filepath': '/workspace/cli.xlsx',
                    **args
                })
                self.assertEqual(actual['stdout'], expected)
                self.assertEqual(
                    ws.execute('test -s /workspace/cli.xlsx; echo $?'), '0\n')
                ws.execute('mv /workspace/cli.xlsx /workspace/moved.xlsx')
                self.assertEqual(
                    cli('excel', 'read_data_from_excel', {
                        'filepath': '/workspace/moved.xlsx',
                        **args
                    })['stdout'], expected)

                args = {
                    'source_path': str(work / 'cv-gboeing.pdf'),
                    'page_numbers': [1],
                    'output_path': str(work / 'direct.pdf')
                }
                await original('pdf-tools', 'extract_pdf_pages', args)
                result = cli(
                    'pdf-tools', 'extract_pdf_pages', {
                        'source_path': '/workspace/cv-gboeing.pdf',
                        'page_numbers': [1],
                        'output_path': '/workspace/cli.pdf'
                    })
                self.assertEqual(result['exit_code'], 0)
                self.assertIn("'/workspace/cli.pdf'", result['stdout'])
                self.assertEqual((work / 'cli.pdf').read_bytes(),
                                 (work / 'direct.pdf').read_bytes())
                # A session survives distinct shell invocations.
                search = cli(
                    'pdf-tools', 'search_pdf_content', {
                        'pdf_file_path': '/workspace/cv-gboeing.pdf',
                        'pattern': 'Boeing',
                        'page_size': 10
                    })['stdout']
                identifier = re.search(r'Search ID: (\S+)', search).group(1)
                info = cli('pdf-tools', 'search_pdf_info',
                           {'search_id': identifier})
                self.assertIn('PDF Path: /workspace/cv-gboeing.pdf',
                              info['stdout'])
                self.assertIn(
                    'Search ID: ' + identifier,
                    cli('pdf-tools', 'search_pdf_go_page', {
                        'search_id': identifier,
                        'page_number': 1
                    })['stdout'])
                # Upstream missing-file errors still identify the virtual path.
                missing = cli('pdf-tools', 'read_pdf_pages',
                              {'pdf_file_path': '/workspace/missing.pdf'})
                expected = await original(
                    'pdf-tools', 'read_pdf_pages',
                    {'pdf_file_path': str(work / 'missing.pdf')})
                self.assertEqual(missing['stdout'],
                                 expected.replace(str(work), '/workspace'))
                for kind, name, key in [
                    ('pdf-tools', 'read_pdf_pages', 'pdf_file_path'),
                    ('excel', 'get_workbook_metadata', 'filepath')
                ]:
                    denied = cli(kind, name, {key: '/etc/passwd'})
                    self.assertNotEqual(denied['exit_code'], 0)
                    self.assertIn('path must be under /workspace',
                                  denied['stderr'])
                self.assertFalse((work / '.runtime').exists())


class OfficeTools(unittest.IsolatedAsyncioTestCase):

    async def test_cli_schemas_reads_and_writes_match_the_original(self):
        for task, kind, file in [('interview-report', 'word',
                                  'Candidates_resumes.docx'),
                                 ('ppt-analysis', 'pptx', 'Compile.pptx')]:
            with self.subTest(kind=kind):
                await self.compare(REPO / 'task/toolathlon' / task, kind, file)

    async def compare(self, task, kind, file):
        with ExitStack() as stack:
            work = Path(stack.enter_context(
                tempfile.TemporaryDirectory())).resolve()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = str(sock.getsockname()[1])
            stack.enter_context(
                patch.dict(os.environ, {
                    'AGENT_WORKSPACE': str(work),
                    'MIRAGE_DAEMON_PORT': port,
                }))
            (work / file).write_bytes(
                (REPO / 'submodule/Toolathlon/tasks/finalpool' / task.name /
                 'initial_workspace' / file).read_bytes())
            clis = yaml.safe_load((task / 'vfs/workspace.yaml').read_text())
            stack.enter_context(
                serve_tools(list(clis['clis']), str(work), task.name))
            ws = Workspace.create(task / 'vfs/workspace.yaml')
            stack.callback(ws.close)
            async with AsyncExitStack() as clients:
                log = stack.enter_context((work / 'test-server.log').open('w'))
                params = launch(SERVERS[kind](Launch(task, str(work))),
                                str(work))
                streams = await clients.enter_async_context(
                    stdio_client(StdioServerParameters(**params), errlog=log))
                session = await clients.enter_async_context(
                    ClientSession(*streams))
                await session.initialize()

                def cli(name, arguments):
                    return ws.execute_result(
                        f'{kind} {name} ' + shlex.quote(json.dumps(arguments)))

                async def original(name, arguments):
                    result = await session.call_tool(name, arguments)
                    return '\n'.join(block.text for block in result.content)

                for tool in (await session.list_tools()).tools:
                    with self.subTest(tool=tool.name):
                        # The CLI spells the tool's underscores as hyphens.
                        spelled = tool.name.replace('_', '-')
                        self.assertEqual(
                            json.loads(
                                ws.execute(f'{kind} {tool.name} --help')),
                            {
                                **tool.model_dump(mode='json',
                                                  exclude_none=True), 'name':
                                spelled
                            })
                        self.assertIn(f'`{kind} {spelled}`',
                                      (task / 'vfs/SKILL.md').read_text())
                if kind == 'word':
                    expected = await original('get_document_text',
                                              {'filename': str(work / file)})
                    actual = cli('get_document_text',
                                 {'filename': '/workspace/' + file})
                    self.assertEqual(actual['exit_code'], 0)
                    self.assertEqual(actual['stdout'], expected)
                    # Upstream starts the server in the workspace, so a
                    # relative name is the workspace's file on both sides.
                    self.assertEqual(
                        await original('get_document_text',
                                       {'filename': file}), expected)
                    self.assertEqual(
                        cli('get_document_text', {'filename': file})['stdout'],
                        expected)
                    listed = await original('list_available_documents', {})
                    self.assertIn(f'- {file} ', listed)
                    self.assertEqual(
                        cli('list_available_documents', {})['stdout'], listed)
                    for name, args in [('create_document', {}),
                                       ('add_paragraph', {
                                           'text': 'parity'
                                       })]:
                        expected = await original(
                            name, {
                                'filename': str(work / 'direct.docx'),
                                **args
                            })
                        actual = cli(name, {
                            'filename': '/workspace/cli.docx',
                            **args
                        })
                        self.assertEqual(
                            actual['stdout'],
                            expected.replace(str(work / 'direct.docx'),
                                             '/workspace/cli.docx'))
                    self.assertEqual(
                        cli('get_document_text',
                            {'filename': '/workspace/cli.docx'})['stdout'],
                        await
                        original('get_document_text',
                                 {'filename': str(work / 'direct.docx')}))
                    denied = cli('get_document_text',
                                 {'filename': '/etc/passwd'})
                else:
                    await original('open_presentation', {
                        'file_path': str(work / file),
                        'id': 'deck'
                    })
                    opened = cli('open_presentation', {
                        'file_path': '/workspace/' + file,
                        'id': 'deck'
                    })
                    self.assertEqual(opened['exit_code'], 0)
                    self.assertNotIn(str(work), opened['stdout'])
                    # The loaded deck survives distinct shell invocations.
                    deck = await original('extract_presentation_text',
                                          {'presentation_id': 'deck'})
                    self.assertEqual(
                        cli('extract_presentation_text',
                            {'presentation_id': 'deck'})['stdout'], deck)
                    # Upstream starts the server in the workspace, so a
                    # relative name opens the workspace's deck on both sides.
                    await original('open_presentation', {
                        'file_path': file,
                        'id': 'relative'
                    })
                    self.assertEqual(
                        cli('open_presentation', {
                            'file_path': file,
                            'id': 'relative'
                        })['exit_code'], 0)
                    for text in [
                            await original('extract_presentation_text',
                                           {'presentation_id': 'relative'}),
                            cli('extract_presentation_text',
                                {'presentation_id': 'relative'})['stdout']
                    ]:
                        self.assertEqual(
                            {
                                **json.loads(text), 'presentation_id': 'deck'
                            }, json.loads(deck))
                    saved = cli(
                        'save_presentation', {
                            'file_path': '/workspace/saved.pptx',
                            'presentation_id': 'deck'
                        })
                    self.assertIn('/workspace/saved.pptx', saved['stdout'])
                    self.assertNotIn(str(work), saved['stdout'])
                    self.assertTrue((work / 'saved.pptx').is_file())
                    denied = cli('open_presentation',
                                 {'file_path': '/etc/passwd'})
                self.assertNotEqual(denied['exit_code'], 0)
                self.assertIn('path must be under /workspace',
                              denied['stderr'])


if __name__ == '__main__':
    unittest.main()
