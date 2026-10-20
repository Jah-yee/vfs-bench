"""Original service tools, shared response transport and separate CLIs."""
import asyncio
import os
import subprocess
import tempfile
import threading
import time
import traceback
from contextlib import ExitStack, contextmanager
from pathlib import Path

from server.seed.business import restore_environment
from server.seed.papers import close

REPO = Path(__file__).resolve().parents[2]
TOOLS = {
    'canvas':
    ('canvas-mcp', 'canvas-mcp-server/build/index.js', 'CANVAS_CLI_URL'),
    'woocommerce':
    ('woocommerce-mcp', '@lockon0927/woocommerce-mcp/dist/index.js',
     'WOOCOMMERCE_CLI_URL'),
    'yahoo-finance': ('yahoo-finance-mcp', None, 'YAHOO_CLI_URL'),
    'google_map':
    ('maps-mcp', '@modelcontextprotocol/server-google-maps/dist/index.js',
     'MAPS_CLI_URL'),
    'youtube': ('youtube-mcp', 'dist/index.js', 'YOUTUBE_CLI_URL'),
    'youtube-transcript': ('youtube-transcript-mcp', None,
                           'TRANSCRIPT_CLI_URL'),
    'rail_12306': ('rail-mcp', '12306-mcp/build/index.js', 'RAIL_CLI_URL'),
    'memory':
    ('memory-mcp', '@modelcontextprotocol/server-memory/dist/index.js',
     'MEMORY_CLI_URL'),
    'emails': ('emails-mcp', None, 'EMAILS_CLI_URL'),
    'howtocook': ('howtocook-mcp', None, 'HOWTOCOOK_CLI_URL'),
    'fetch': ('fetch-mcp', None, 'FETCH_CLI_URL'),
    'notion': ('notion-mcp', None, 'NOTION_CLI_URL'),
    'wandb': ('wandb-mcp', None, 'WANDB_CLI_URL'),
    'snowflake': ('snowflake-mcp', None, 'SNOWFLAKE_CLI_URL'),
    'google-cloud': ('google-cloud-mcp', None, 'GOOGLE_CLOUD_CLI_URL'),
}
# Served through an MCP client on the arm's own launch rather than imported
# handlers: notion's bundle carries its own copy of the SDK, so the handler
# hook in original_tools.mjs never sees its Server; snowflake and
# google-cloud configure and run their servers inside `main()`, so there is
# no app to import. The client is `original_tools.serve_client`, called on a
# thread of this process; only the server is a child.
CLIENT_KINDS = ('notion', 'snowflake', 'google-cloud', 'pdf-tools', 'excel',
                'word', 'pptx', 'emails', 'wandb')
GOOGLE_TOOLS = {
    'google_calendar': ('calendar-mcp', None, 'CALENDAR_CLI_URL'),
    'google_sheet': ('google-sheets-mcp', None, 'SHEETS_CLI_URL'),
}
DOCUMENT_TOOLS = {
    'pdf-tools': ('pdf-tools-mcp', None, 'PDF_TOOLS_CLI_URL'),
    'excel': ('', None, 'EXCEL_CLI_URL'),
    'word': ('', None, 'WORD_CLI_URL'),
    'pptx': ('', None, 'PPTX_CLI_URL'),
}


def parameters(kind, workdir, task=None):
    if kind in ('emails', 'fetch', 'notion', 'snowflake', 'google-cloud',
                'wandb'):
        # Each reads the task: emails for its workspace, fetch for its
        # capture (the research flavour is its own transport, in
        # server/seed/research.py), notion for its workspace and page,
        # snowflake for its one allowed database, google-cloud for its
        # four allow-lists.
        if task is None:
            raise ValueError('The ' + kind +
                             ' CLI requires a task configuration')
        from server.mcp.mcp_servers import SERVERS, Launch
        return SERVERS[kind](Launch(REPO / 'task/toolathlon' / task, workdir))
    if kind in ('canvas', 'woocommerce', 'howtocook', *DOCUMENT_TOOLS,
                *GOOGLE_TOOLS):
        from server.mcp.mcp_servers import SERVERS, Launch
        return SERVERS[kind](Launch(REPO / 'task/toolathlon', workdir))
    from server.mcp.setup_travel_video import SOURCES, source_root
    if kind == 'yahoo-finance':
        # The launch the MCP arm runs too: the original SDK, live, as
        # upstream reads it, in the vendored lock's environment, which
        # `uv run` creates on a fresh checkout. The redirect sends each read
        # through the recording transport once YAHOO_CLI_URL names it.
        source = (REPO / 'submodule/toolathlon_gym/local_servers/'
                  'yahoo-finance-mcp/server.py')
        return {
            'command':
            'uv',
            'args': [
                'run', '--locked', '--directory',
                str(REPO / 'vendor/yahoo-finance-mcp'), 'python', '-c',
                "import "
                "runpy,sys;runpy.run_path(sys.argv[1],run_name='__main__')",
                str(source)
            ],
            'cwd':
            workdir,
            'env': {
                **os.environ, 'PYTHONPATH':
                str(REPO / 'redirect/yahoo_capture')
            }
        }
    vendor, entry, _ = TOOLS[kind]
    source = (source_root(vendor) if kind != 'memory' else REPO /
              'vendor/memory-mcp')
    env = {**os.environ}
    if kind in ('google_map', 'youtube'):
        env['GOOGLE_MAPS_API_KEY' if kind ==
            'google_map' else 'YOUTUBE_API_KEY'] = 'fixture'
    if kind == 'memory':
        env['MEMORY_FILE_PATH'] = str(Path(workdir) / 'memory/memory.json')
    if kind == 'youtube-transcript':
        return {
            'command': str(source / '.venv/bin/python'),
            'args': ['-m', 'mcp_youtube_transcript'],
            'cwd': workdir,
            'env': env
        }
    base = source if vendor in SOURCES else source / 'node_modules'
    path = base / entry
    if not path.is_file():
        raise FileNotFoundError(
            'Install original tools: python -m server.mcp.setup_travel_video')
    args = [str(path)]
    if kind in ('google_map', 'youtube', 'rail_12306'):
        args = [
            '--import',
            str(REPO / 'redirect/public_services/hook.mjs'), *args
        ]
    return {'command': 'node', 'args': args, 'cwd': workdir, 'env': env}


@contextmanager
def serve(task, workdir):
    from task.toolathlon import needed_mcp_servers
    kinds = [kind for kind in needed_mcp_servers(task) if kind in TOOLS]
    with serve_tools(kinds, workdir, task) as record:
        yield record


def client_thread(kind,
                  endpoint,
                  params,
                  log,
                  virtual_root='/work',
                  tools=None):
    """Serve one client kind on a thread; returns the thread and its stop.

    The server is the child, launched confined exactly as the MCP arm
    launches it; the MCP client speaking to it and the HTTP front the CLI
    reads are `original_tools.serve_client`, running here. A failure to
    start ends the thread, with its traceback in the log the caller reads.

    Closing has two steps, because the stop event is only read once the
    client is serving: a server that hangs before it answers `initialize`
    would never see it, and the process this call started would outlive
    the run the way it could not when the transport was a subprocess this
    module held. So the task is cancelled where the event does not reach
    it, which unwinds the MCP client and takes the child's process tree
    with it.
    """
    from server.clients.original_tools import serve_client
    stop = threading.Event()
    running = {}

    def run():

        async def serving():
            """Publish what teardown cancels, then serve."""
            running['loop'] = asyncio.get_running_loop()
            running['task'] = asyncio.current_task()
            await serve_client(kind, endpoint, params, log, stop, virtual_root,
                               tools)

        try:
            asyncio.run(serving())
        except asyncio.CancelledError:
            pass
        except BaseException:  # noqa: BLE001 -- reported through the log
            log.write(traceback.format_exc())
            log.flush()
            raise

    thread = threading.Thread(target=run, name='original-' + kind, daemon=True)
    thread.start()

    def close():
        """Ask, then cancel; either way the child goes with the thread."""
        stop.set()
        thread.join(timeout=10)
        task, loop = running.get('task'), running.get('loop')
        if thread.is_alive() and task is not None:
            loop.call_soon_threadsafe(task.cancel)
            thread.join(timeout=20)

    return thread, close


@contextmanager
def serve_tools(kinds, workdir, task=None):
    """Call the pinned foreign handlers over the existing CLI transport."""
    from server.execution import launch
    definitions = {**TOOLS, **GOOGLE_TOOLS, **DOCUMENT_TOOLS}
    saved = {
        definitions[kind][2]: os.environ.get(definitions[kind][2])
        for kind in kinds
    }
    (REPO / 'state/research').mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        stack.callback(restore_environment, saved)
        directory = Path(
            stack.enter_context(
                tempfile.TemporaryDirectory(prefix='original-tools-',
                                            dir=REPO / 'state/research')))
        from task.toolathlon import shell_cwd
        virtual_root = (shell_cwd(task) if task else None) or '/work'
        for kind in kinds:
            params = parameters(kind, workdir, task)
            live = False
            endpoint = directory / (kind + '.endpoint')
            readable = [
                *([REPO / 'vendor' /
                   definitions[kind][0]] if definitions[kind][0] else []),
                REPO / 'server/clients/original_tools.mjs',
                *([REPO / 'redirect/gws_calendar'] if kind == 'google_calendar'
                  else []), REPO / 'redirect/yahoo_capture',
                *([REPO / 'server/clients', REPO / 'server/__init__.py']
                  if kind in ('yahoo-finance', 'snowflake',
                              'google-cloud') else [])
            ]
            logpath = directory / (kind + '.log')
            log = stack.enter_context(logpath.open('w'))
            if kind in CLIENT_KINDS:
                # pdf-tools downloads a PDF given by URL, as upstream's
                # does with its network; see `mcp_servers.pdf_tools`.
                started = client_thread(
                    kind, endpoint,
                    launch(params,
                           workdir,
                           readable,
                           public_network=kind == 'pdf-tools'), log,
                    virtual_root)
                stack.callback(started[1])
                for _ in range(600):
                    if endpoint.exists():
                        os.environ[definitions[kind][2]] = endpoint.read_text()
                        break
                    if not started[0].is_alive():
                        raise RuntimeError(logpath.read_text())
                    time.sleep(.1)
                else:
                    raise TimeoutError('Original ' + kind +
                                       ' CLI did not start: ' +
                                       logpath.read_text())
                continue
            original_entry = params['args'][-1]
            if kind in ('youtube-transcript', 'yahoo-finance', 'google_sheet'):
                if kind == 'google_sheet':
                    # Keep the original locked uv environment and redirect.
                    # Import our bridge in that foreign interpreter.
                    params['args'] = params['args'][:-1] + [
                        'python', '-c', 'import asyncio,runpy,sys; '
                        'm=runpy.run_path(sys.argv[1]); '
                        'asyncio.run(m["main"](sys.argv[2],sys.argv[3]))',
                        str(REPO / 'server/clients/original_tools.py'), kind,
                        str(endpoint)
                    ]
                elif kind == 'yahoo-finance':
                    # Keep `uv run`; only the `-c` entry gives way to the
                    # bridge, which reads the SDK live itself.
                    index = params['args'].index('python')
                    params['args'] = [
                        *params['args'][:index + 1],
                        str(REPO / 'server/clients/original_tools.py'), kind,
                        str(endpoint), original_entry
                    ]
                    params['env'].pop('PYTHONPATH', None)
                    live = True
                else:
                    params['args'] = [
                        str(REPO / 'server/clients/original_tools.py'), kind,
                        str(endpoint)
                    ]
                if params['command'] == 'uv':
                    from server.execution import prepare
                    prepare(params)
            else:
                params['args'] = [
                    *params['args'][:-1], '--input-type=module', '-e',
                    'const {serveOriginal} = await import(' + repr(
                        (REPO / 'server/clients/original_tools.mjs').as_uri())
                    + '); await serveOriginal(...process.argv.slice(1));',
                    original_entry,
                    str(endpoint), virtual_root
                ]
            params = launch(
                params,
                workdir,
                readable=readable,
                writable=[directory],
                public_network=kind in ('youtube-transcript', 'youtube')
                or live)
            process = subprocess.Popen([params['command'], *params['args']],
                                       cwd=workdir,
                                       env=params['env'],
                                       stdout=log,
                                       stderr=log)
            stack.callback(close, process)
            for _ in range(600):
                if endpoint.exists():
                    os.environ[definitions[kind][2]] = endpoint.read_text()
                    break
                if process.poll() is not None:
                    raise RuntimeError(logpath.read_text())
                time.sleep(.1)
            else:
                raise TimeoutError('Original ' + kind +
                                   ' CLI did not start: ' +
                                   logpath.read_text())
        yield {
            'tools': kinds,
            'transport': 'original handlers; live service data, nothing kept'
        }
