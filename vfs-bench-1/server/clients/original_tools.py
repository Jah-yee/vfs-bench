"""Expose a foreign server's tools directly to a CLI.

Two doors, one HTTP front. `main` imports a FastMCP server's handlers and
calls them in the foreign interpreter this file is run in. `serve_client` is
for a server whose handlers cannot be imported -- a Go binary, a bundle that
carries its own SDK, a package that builds its server inside `main()` -- and
is a function the transport calls in its own process: it runs the MCP arm's
own launch as the child and speaks to it as an MCP client over stdio. Either
way the CLI reads the same `/tools` and `/call`, and the tool names, schemas
and replies are the server's own.
"""
import argparse
import asyncio
import atexit
import json
import os
import runpy
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace


def emails_app(argv):
    """Build emails-mcp's FastMCP app around its unchanged tool handlers."""
    from emails_mcp.config import config_manager
    from emails_mcp.server import create_services
    from emails_mcp.tools import (register_email_tools, register_folder_tools,
                                  register_management_tools)
    from mcp.server.fastmcp import FastMCP

    # These are the original server's four workspace arguments. The transport
    # replaces stdio only; mcp_servers.emails still supplies their values.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--attachment_upload_path')
    parser.add_argument('--attachment_download_path')
    parser.add_argument('--email_export_path')
    parser.add_argument('--config_file', default='test_emils.json')
    args = parser.parse_args(argv)

    config_manager.load_workspace_config(
        attachment_upload_path=args.attachment_upload_path,
        attachment_download_path=args.attachment_download_path,
        email_export_path=args.email_export_path,
        config_file=args.config_file)
    email_config = config_manager.load_email_config(args.config_file)
    email_service, folder_service, search_service, draft_service = (
        create_services(email_config))
    app = FastMCP('emails-mcp')
    register_email_tools(app, email_service)
    register_folder_tools(app, folder_service)
    register_management_tools(app, draft_service, email_service)
    return app, email_service.cleanup


def host(path, workspace=None, virtual_root='/work'):
    """Translate a confined virtual path into the handler's workspace.

    The virtual root is the task's workspace cwd; legacy callers use /work.
    Absolute host paths and relative or symlink escapes are rejected.
    """
    if not isinstance(path, str):
        return path
    workspace = Path(workspace) if workspace else Path.cwd()
    if path == virtual_root:
        return str(workspace)
    if path.startswith(virtual_root + '/'):
        relative = path.removeprefix(virtual_root + '/')
    elif path.startswith('/'):
        raise ValueError(f'path must be under {virtual_root}: ' + path)
    else:
        relative = path
    if not relative:
        return str(workspace)
    parts = relative.split('/')
    if any(not part or part in ('.', '..') for part in parts):
        raise ValueError(f'invalid {virtual_root} path: ' + path)
    workspace = workspace.resolve()
    target = (workspace / relative).resolve()
    if not target.is_relative_to(workspace):
        raise ValueError(f'path escapes {virtual_root}: ' + path)
    return str(target)


# The google-cloud tools that name a file: the CLI's caller writes paths
# under the task's workspace root, the server reads and writes the host
# directory it runs in.
CLOUD_FILE_ARGUMENTS = {
    'storage_upload_file': 'source_file_path',
    'storage_download_file': 'destination_file_path',
    'bigquery_load_csv_data': 'csv_file_path',
}


def cloud_workspace_request(body, workspace=None, virtual_root='/work'):
    """Map a file argument's workspace path onto the server's directory."""
    if not isinstance(body, dict) or not isinstance(body.get('arguments'),
                                                    dict):
        return body
    key = CLOUD_FILE_ARGUMENTS.get(body.get('name'))
    if key is None or key not in body['arguments']:
        return body
    return {
        **body, 'arguments': {
            **body['arguments'], key:
            host(body['arguments'][key], workspace, virtual_root=virtual_root)
        }
    }


def cloud_workspace_response(operation,
                             result,
                             workspace=None,
                             virtual_root='/work'):
    """Render the server's directory as the workspace root in a reply."""
    if operation not in CLOUD_FILE_ARGUMENTS:
        return result
    directory = str(Path(workspace) if workspace else Path.cwd())
    for block in result.get('content', []):
        if block.get('type') == 'text' and isinstance(block.get('text'), str):
            block['text'] = block['text'].replace(directory, virtual_root)
    return result


def email_workspace_request(body, virtual_root='/work', workspace=None):
    """Map the VFS workspace path onto the handler process's workspace."""
    if not isinstance(body, dict):
        return body
    name = body.get('name')
    original_arguments = body.get('arguments')
    if not isinstance(original_arguments, dict):
        return body
    arguments = dict(original_arguments)

    if name == 'send_email' and isinstance(arguments.get('attachments'), list):
        arguments['attachments'] = [
            host(path, workspace, virtual_root=virtual_root)
            for path in arguments['attachments']
        ]
    if name == 'import_emails' and 'import_path' in arguments:
        arguments['import_path'] = host(arguments['import_path'],
                                        workspace,
                                        virtual_root=virtual_root)
    return {**body, 'arguments': arguments}


def email_workspace_response(operation,
                             result,
                             virtual_root='/work',
                             workspace=None):
    """Render file-operation paths in the VFS namespace.

    The pinned handlers return human-readable strings for every tool. Only
    four operations can put the handler's workspace path in those strings:
    download/export return a saved path, while import/send can echo an input
    path in an error. Email bodies, subjects and search queries are ordinary
    content and must remain byte-for-byte unchanged.
    """
    host = str(Path(workspace) if workspace else Path.cwd())

    def virtual(value):
        if not isinstance(value, str):
            return value
        path_result = (operation == 'download_attachment' and
                       (" saved to: " in value
                        or value.startswith('Error downloading attachment:'))
                       or operation == 'export_emails' and
                       (value.startswith('Successfully exported ')
                        or value.startswith('Error exporting emails:'))
                       or operation == 'import_emails' and
                       (value.startswith('No emails found in import file ')
                        or value.startswith('Error importing emails:'))
                       or operation == 'send_email'
                       and value.startswith('Error sending email:'))
        return value.replace(host, virtual_root) if path_result else value

    for block in result.get('content', []):
        if block.get('type') == 'text':
            block['text'] = virtual(block.get('text'))
    structured = result.get('structuredContent')
    if isinstance(structured, dict) and 'result' in structured:
        structured['result'] = virtual(structured['result'])
    return result


async def serve_client(kind,
                       endpoint,
                       params,
                       log=None,
                       stop=None,
                       virtual_root='/work',
                       tools=None):
    """Run upstream's server as a child and answer the CLI as its client.

    The child is the MCP arm's launch verbatim -- command, arguments,
    environment, working directory, confinement -- so nothing about the
    server is restated here; the one difference from that arm is who is
    on the other end of its stdio. Returns once `stop` is set, taking the
    child down with it.

    `tools`, when given, is the MCP arm's own filter: the server's names
    for the tools a dataset hands the task, which is all the CLI lists and
    all it will call. None is every tool the server has, which is what a
    dataset that names servers rather than tools gives its arm.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    child = StdioServerParameters(command=params['command'],
                                  args=params['args'],
                                  env=params.get('env'),
                                  cwd=params.get('cwd'))
    # The child's directory is the workspace the CLI's caller calls
    # `virtual_root`; this process's own is not.
    workspace = params['cwd']
    async with stdio_client(child, errlog=log or sys.stderr) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def invoke(path, body):
                if path == '/tools':
                    result = await session.list_tools()
                    if tools is not None:
                        result.tools = [
                            tool for tool in result.tools if tool.name in tools
                        ]
                else:
                    if tools is not None and body.get('name') not in tools:
                        raise ValueError(f'Unknown {kind} command: '
                                         f'{body.get("name")}')
                    if kind == 'google-cloud':
                        body = cloud_workspace_request(body, workspace,
                                                       virtual_root)
                    elif kind in DOCUMENT_KINDS:
                        body = document_workspace_request(
                            kind, body, workspace)
                    elif kind == 'emails':
                        body = email_workspace_request(body, virtual_root,
                                                       workspace)
                    result = await session.call_tool(body['name'],
                                                     body.get('arguments'))
                rendered = result.model_dump(mode='json', exclude_none=True)
                if kind == 'google-cloud' and path == '/call':
                    rendered = cloud_workspace_response(
                        body.get('name'), rendered, workspace, virtual_root)
                elif kind in DOCUMENT_KINDS and path == '/call':
                    rendered = document_workspace_response(
                        kind, body.get('name'), rendered, workspace)
                elif kind == 'emails' and path == '/call':
                    rendered = email_workspace_response(
                        body.get('name'), rendered, virtual_root, workspace)
                return rendered

            await serve(kind, endpoint, invoke, stop=stop)


# The arguments that name a file, by server; a tool missing from a
# per-tool table takes none. pptx's `image_source` is a path only when its
# `source_type` is the default "file"; it may otherwise be base64.
DOCUMENT_PATH_ARGUMENTS = {
    'excel': ('filepath', ),
    'pdf-tools': {
        'read_pdf_pages': ('pdf_file_path', ),
        'get_pdf_info': ('pdf_file_path', ),
        'search_pdf_content': ('pdf_file_path', ),
        'merge_pdfs': ('pdf_paths', 'output_path'),
        'extract_pdf_pages': ('source_path', 'output_path'),
    },
    'word': ('filename', 'source_filename', 'destination_filename',
             'output_filename', 'image_path', 'directory'),
    'pptx': ('file_path', 'template_path', 'image_source', 'image_paths',
             'output_path', 'font_path'),
}
DOCUMENT_KINDS = tuple(DOCUMENT_PATH_ARGUMENTS)

# What word and pptx return as document content, verbatim. Every other reply
# is a status message that echoes the path it was given.
DOCUMENT_TEXT = {
    'word': {
        'get_document_text', 'get_document_xml', 'get_document_outline',
        'get_paragraph_text_from_document', 'find_text_in_document',
        'get_all_comments', 'get_comments_by_author',
        'get_comments_for_paragraph'
    },
    'pptx':
    {'extract_slide_text', 'extract_presentation_text', 'get_slide_info'},
}


def document_workspace_request(kind, body, workspace):
    """Translate document path arguments, leaving data and schemas untouched.

    Relative paths and URLs retain the upstream handler's interpretation.
    Absolute paths must name the disk mount, including symlink resolution;
    the original child additionally runs under the MCP arm's confinement.
    """
    if not isinstance(body, dict) or not isinstance(body.get('arguments'),
                                                    dict):
        return body
    keys = DOCUMENT_PATH_ARGUMENTS[kind]
    if isinstance(keys, dict):
        keys = keys.get(body.get('name'), ())
    if body['arguments'].get('source_type', 'file') != 'file':
        keys = tuple(key for key in keys if key != 'image_source')
    root = Path(workspace).resolve()

    def path(value):
        if isinstance(value, list):
            return [path(item) for item in value]
        if isinstance(value, dict):
            return {role: path(item) for role, item in value.items()}
        if not isinstance(value, str):
            return value
        if value.startswith(('http://', 'https://')):
            return value
        if not value.startswith('/'):
            if not (root / value).resolve().is_relative_to(root):
                raise ValueError('path escapes /workspace: ' + value)
            return value
        if value != '/workspace' and not value.startswith('/workspace/'):
            raise ValueError('path must be under /workspace: ' + value)
        target = (root /
                  value.removeprefix('/workspace').lstrip('/')).resolve()
        if not target.is_relative_to(root):
            raise ValueError('path escapes /workspace: ' + value)
        return str(target)

    return {
        **body, 'arguments': {
            key: path(value) if key in keys else value
            for key, value in body['arguments'].items()
        }
    }


def document_workspace_response(kind, operation, result, workspace):
    """Translate status paths, never document text, cell data or matches."""
    root = str(Path(workspace).resolve())

    def text(value):
        if not isinstance(value, str):
            return value
        if (result.get('isError') or value.startswith('Error')
                or kind == 'excel' and operation == 'create_workbook'
                or kind == 'pdf-tools'
                and operation in ('merge_pdfs', 'extract_pdf_pages')
                or kind in DOCUMENT_TEXT
                and operation not in DOCUMENT_TEXT[kind]):
            return value.replace(root, '/workspace')
        if kind == 'pdf-tools' and operation == 'search_pdf_info':
            return value.replace('PDF Path: ' + root, 'PDF Path: /workspace',
                                 1)
        return value

    for block in result.get('content', []):
        if block.get('type') == 'text':
            block['text'] = text(block.get('text'))
    structured = result.get('structuredContent')
    if isinstance(structured, dict) and 'result' in structured:
        structured['result'] = text(structured['result'])
    return result


async def main(kind, endpoint, virtual_root='/work'):
    from mcp import types
    from mcp.server.lowlevel.server import request_ctx

    if kind == 'youtube-transcript':
        from mcp_youtube_transcript import server
        app = server(*(os.environ.get(key)
                       for key in ('WEBSHARE_PROXY_USERNAME',
                                   'WEBSHARE_PROXY_PASSWORD', 'HTTP_PROXY',
                                   'HTTPS_PROXY')))
    elif kind == 'yahoo-finance':
        app = runpy.run_path(sys.argv[3])['yfinance_server']
    elif kind == 'google_sheet':
        from mcp_google_sheets.server import mcp as app
    elif kind == 'emails':
        app, cleanup = emails_app(sys.argv[3:])
        atexit.register(cleanup)
    else:
        raise ValueError('Unknown original server')
    capture = None
    if kind == 'yahoo-finance':
        # The original SDK, read live for every call; nothing is kept.
        sys.path.insert(
            0,
            str(
                Path(__file__).resolve().parents[2] /
                'redirect/yahoo_capture'))
        import capture
    original = app._mcp_server
    async with original.lifespan(original) as context:

        async def invoke(path, body):
            if kind == 'emails' and path == '/call':
                body = email_workspace_request(body, virtual_root)
            request = (types.ListToolsRequest(
                method='tools/list') if path == '/tools' else
                       types.CallToolRequest(method='tools/call', params=body))
            token = request_ctx.set(
                SimpleNamespace(request_id=0,
                                meta=None,
                                session=None,
                                lifespan_context=context))
            try:
                result = await original.request_handlers[type(request)
                                                         ](request)
                rendered = result.root.model_dump(mode='json',
                                                  exclude_none=True)
                return (email_workspace_response(body.get('name'), rendered,
                                                 virtual_root)
                        if kind == 'emails' and path == '/call' else rendered)
            finally:
                request_ctx.reset(token)

        await serve(kind, endpoint, invoke, capture)


async def serve(kind, endpoint, invoke, capture=None, stop=None):
    """Answer `/tools` and `/call` over HTTP by awaiting `invoke`.

    Serves until the process ends, or until `stop` -- a threading.Event,
    for a caller in whose process this runs -- is set.
    """
    loop = asyncio.get_running_loop()

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond(None)

        def do_POST(self):
            self.respond(
                json.loads(self.rfile.read(int(
                    self.headers['Content-Length']))))

        def respond(self, body):
            if self.path == '/sdk' and kind == 'yahoo-finance':
                self.sdk(body)
                return
            if self.path not in ('/tools', '/call'):
                self.send_error(404)
                return
            try:
                result = asyncio.run_coroutine_threadsafe(
                    invoke(self.path, body), loop).result()
                status = 200
            except Exception as error:
                result, status = {'error': str(error)}, 500
            data = json.dumps(result).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def sdk(self, body):
            import hashlib
            from datetime import datetime, timezone
            try:
                allowed = capture.PROPERTIES | capture.METHODS
                if body['name'] not in allowed:
                    raise ValueError('Unknown Yahoo read')
                request = {'sdk_version': capture.yf.__version__, **body}
                key = hashlib.sha256(
                    json.dumps(request, sort_keys=True).encode()).hexdigest()
                ticker = capture.REAL_TICKER(body['ticker'])
                value = getattr(ticker, body['name'])
                if body['name'] in capture.METHODS:
                    value = value(*capture.decode(body['args']),
                                  **capture.decode(body['kwargs']))
                encoded = capture.encode(value)
                record = {
                    'request':
                    request,
                    'value':
                    encoded,
                    'source':
                    'live',
                    'fetched_at':
                    datetime.now(timezone.utc).isoformat(),
                    'sha256':
                    hashlib.sha256(
                        json.dumps(encoded,
                                   sort_keys=True).encode()).hexdigest()
                }
                result = {
                    'value': record['value'],
                    'snapshot': {
                        'key': key,
                        **{
                            k: v
                            for k, v in record.items() if k != 'value'
                        }
                    }
                }
            except Exception as error:
                result = {'error': str(error)}
            data = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    if capture is not None:
        capture.install(os.environ['PUBLIC_SERVICE_URL'] + '/yahoo')
    Path(endpoint).write_text('http://127.0.0.1:' + str(server.server_port))
    if stop is None:
        await asyncio.to_thread(server.serve_forever)
        return
    serving = asyncio.create_task(asyncio.to_thread(server.serve_forever))
    await asyncio.to_thread(stop.wait)
    server.shutdown()
    await serving


if __name__ == '__main__':
    # Run as a script, this directory is sys.path[0], and its fixture
    # clients are named after the SDKs they stand in for; drop it so the
    # server's own imports are what resolve. Only here: imported as a
    # module, the process's path is not ours to edit.
    if str(Path(__file__).parent) in sys.path:
        sys.path.remove(str(Path(__file__).parent))
    asyncio.run(main(sys.argv[1], sys.argv[2]))
