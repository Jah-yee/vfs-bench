import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import patch

import yaml

REPO = Path(__file__).resolve().parents[3]
for directory in ('', 'agent', 'task'):
    sys.path.insert(0, str(REPO / directory))
from setup.task_surfaces import ATLAS_CLI_TOOLS  # noqa: E402
from task.mcpatlas import TOOL_COMMANDS  # noqa: E402

TASKS = REPO / 'task/mcpatlas'


def tool_clis(task):
    """The task's CLIs that are its MCP servers' tools as commands."""
    clis = (yaml.safe_load((TASKS / task / 'vfs/workspace.yaml').read_text())
            or {}).get('clis') or {}
    return [name for name in clis if name in TOOL_COMMANDS]


def decoded(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def listed(task):
    """What each tool CLI lists in the task's own shell, as the model sees.

    Seeded, served and built the way `arms.build_arm` builds the shell arm.
    Each CLI lists only the tools Atlas's row enables, so the catalog keeps
    each task's own listing: `<cli> --help` names the commands and
    `<cli> <command> --help` returns the description and input schema the
    CLI's server advertises.
    """
    import arms
    import dataset
    from workspace import Workspace, config_for

    dataset.use('mcpatlas')
    task_dir = dataset.local(task)
    with tempfile.TemporaryDirectory() as scratch, patch.dict(
            os.environ, AGENT_WORKSPACE=str(Path(scratch) / task)):
        subprocess.run(
            [sys.executable, str(dataset.seeder()), task],
            cwd=REPO,
            check=True)
        workdir = arms.mirage_env(task_dir)
        found = {}

        async def read():
            async with AsyncExitStack() as stack:
                arms.open_services(task_dir, workdir, stack)
                shell = Workspace.create(config_for(task_dir))
                stack.callback(shell.close)
                for cli in tool_clis(task):
                    listing = shell.execute_result(f'{cli} --help')
                    if listing.get('exit_code'):
                        raise RuntimeError(f'{task}: `{cli} --help` failed: '
                                           f"{listing.get('stderr')}")
                    tools = []
                    for line in (listing.get('stdout')
                                 or '').strip().splitlines()[2:]:
                        match = re.match(r'^([A-Za-z0-9_.\-]+):( |$)', line)
                        answer = match and decoded(
                            shell.execute(f'{cli} {match.group(1)} --help'))
                        if isinstance(answer, dict) and ('inputSchema'
                                                         in answer):
                            tools.append({**answer, 'name': match[1]})
                    if not tools:
                        raise RuntimeError(f'{task}: `{cli} --help` listed '
                                           'no tools')
                    found[cli] = [{
                        'command': tool['name'],
                        'description': tool.get('description') or '',
                        'inputSchema': tool.get('inputSchema'),
                    } for tool in tools]

        asyncio.run(read())
    return found


def capture(tasks):
    from dotenv import load_dotenv
    load_dotenv(REPO / '.env.development')
    catalog = (json.loads(ATLAS_CLI_TOOLS.read_text())
               if ATLAS_CLI_TOOLS.exists() else {})
    for task in tasks:
        catalog[task] = listed(task)
        ATLAS_CLI_TOOLS.parent.mkdir(parents=True, exist_ok=True)
        ATLAS_CLI_TOOLS.write_text(
            json.dumps(
                dict(sorted(catalog.items())), indent=1, ensure_ascii=False) +
            '\n')
        print(task, flush=True)


if __name__ == '__main__':
    capture(sys.argv[1:]
            or sorted(path.parts[-3]
                      for path in TASKS.glob('*/vfs/workspace.yaml')
                      if tool_clis(path.parts[-3])))
