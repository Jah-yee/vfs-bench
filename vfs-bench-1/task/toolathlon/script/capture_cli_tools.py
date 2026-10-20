import asyncio
import json
import os
import re
import subprocess
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import patch

import yaml

REPO = Path(__file__).resolve().parents[3]
for directory in ('', 'agent', 'task'):
    sys.path.insert(0, str(REPO / directory))
from setup.task_surfaces import CLI_TOOLS, NATIVE  # noqa: E402

TASKS = REPO / 'task/toolathlon'


def tool_clis(task):
    """The task's CLIs that are its MCP servers' tools as commands."""
    clis = (yaml.safe_load((TASKS / task / 'vfs/workspace.yaml').read_text())
            or {}).get('clis') or {}
    return [name for name in clis if name not in NATIVE]


def cover():
    """Few tasks that between them carry every tool CLI."""
    carried = {
        path.parts[-3]: set(tool_clis(path.parts[-3]))
        for path in sorted(TASKS.glob('*/vfs/workspace.yaml'))
    }
    needed, chosen = set().union(*carried.values()), []
    while needed:
        task = max(carried, key=lambda name: len(carried[name] & needed))
        chosen.append(task)
        needed -= carried[task]
    return chosen


def decoded(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def listed(task):
    """What each tool CLI lists in the task's own shell, as the model sees.

    Seeded, served and built the way `arms.build_arm` builds the shell arm;
    `<cli> --help` names the commands and `<cli> <command> --help` returns
    the description and input schema the CLI's server advertises.
    """
    import arms
    import dataset
    import services
    from workspace import Workspace, config_for

    dataset.use('toolathlon')
    task_dir = dataset.local(task)
    with patch.dict(os.environ,
                    AGENT_WORKSPACE=str(services.workspaces_dir() / task)):
        workdir = arms.mirage_env(task_dir)
        subprocess.run(
            [sys.executable, str(dataset.seeder()), task],
            cwd=REPO,
            check=True)
        services.load_stack_env(override=True)
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
                    text = listing.get('stdout') or ''
                    # `huggingface` answers with its server's tool list as
                    # JSON.
                    tools = decoded(text)
                    if not isinstance(tools, list):
                        tools = []
                        for line in text.strip().splitlines()[2:]:
                            match = re.match(r'^([A-Za-z0-9_.\-]+):( |$)',
                                             line)
                            answer = match and decoded(
                                shell.execute(
                                    f'{cli} {match.group(1)} --help'))
                            if isinstance(answer, dict) and ('inputSchema'
                                                             in answer):
                                tools.append({**answer, 'name': match[1]})
                    found[cli] = [{
                        'command': tool['name'],
                        'description': tool.get('description') or '',
                        'inputSchema': tool.get('inputSchema'),
                    } for tool in tools]

        asyncio.run(read())
    return found


def capture(tasks):
    import services
    from dotenv import load_dotenv
    load_dotenv(REPO / '.env.development')
    services.load_stack_env()
    catalog = json.loads(CLI_TOOLS.read_text()) if CLI_TOOLS.exists() else {}
    for task in tasks:
        catalog.update(listed(task))
        CLI_TOOLS.write_text(
            json.dumps(
                dict(sorted(catalog.items())), indent=1, ensure_ascii=False) +
            '\n')
        print(task, flush=True)


if __name__ == '__main__':
    capture(sys.argv[1:] or cover())
