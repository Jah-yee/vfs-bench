"""Direct CLI entry into locked paper server handlers."""
import asyncio
import importlib.util
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def main(kind, source):
    if kind == 'arxiv-latex':
        original = load(Path(source) / 'arxiv-latex-mcp.py', 'original_latex')
        list_tools, call_tool = original.mcp.list_tools, original.mcp.call_tool
    elif kind == 'arxiv_local':
        load(Path(source) / 'original_wrapper.py', 'original_wrapper')
        from arxiv_mcp_server import server as original
        list_tools, call_tool = original.list_tools, original.call_tool
    elif kind == 'scholarly':
        from mcp_scholarly import server as original
        list_tools = original.handle_list_tools
        call_tool = original.handle_call_tool
    else:
        raise ValueError('Unknown original paper server')

    async def invoke(path, arguments):
        if path == '/tools':
            return {
                'tools': [
                    tool.model_dump(mode='json', exclude_none=True)
                    for tool in await list_tools()
                ]
            }
        if path != '/call':
            raise ValueError('Unknown CLI transport path')
        # Scholarly notifies an MCP session before searching. CLI has no
        # notification channel; its original handler and result stay intact.
        token = None
        if kind == 'scholarly':
            from mcp.server import request_ctx

            async def notify():
                pass

            token = request_ctx.set(
                SimpleNamespace(session=SimpleNamespace(
                    send_resource_list_changed=notify)))
        try:
            result = await call_tool(arguments['name'],
                                     arguments.get('arguments', {}))
            return {
                'content': [
                    block.model_dump(mode='json', exclude_none=True)
                    for block in result
                ]
            }
        finally:
            if token is not None:
                request_ctx.reset(token)

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
            try:
                result = asyncio.run_coroutine_threadsafe(
                    invoke(self.path, body), loop).result(timeout=180)
                status = 200
            except Exception as error:
                result, status = {'error': str(error)}, 500
            data = json.dumps(result).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    # The package may write progress messages to stdout; readiness uses a file.
    Path(os.environ['PAPER_CLI_ENDPOINT']).write_text('http://127.0.0.1:' +
                                                      str(server.server_port))
    await asyncio.to_thread(server.serve_forever)


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], sys.argv[2]))
