import asyncio
import os
import sys

from mirage.io.stream import yield_bytes
from mirage.io.types import materialize
from mirage.workspace.cli.types import CLIInstall
from mirage.workspace.executor.command.cli import handle_cli
from mirage.workspace.session.session import SessionState


async def dispatch(name: str, cli, config, argv: list[str],
                   stdin: bool) -> int:
    """Run one command line through mirage and write out its streams.

    Args:
        name (str): the CLI's head word.
        cli: its `CLI`.
        config: the config instance the CLI's `config_model` expects.
        argv (list[str]): the words after the head word.
        stdin (bool): whether to forward this process's standard input.

    Returns:
        int: the command's exit status.
    """
    piped = None
    if stdin:
        # A terminal stdin is not an empty body, it is no body, and reading
        # it would block; the shim only ever pipes, so this matters when the
        # module is run by hand.
        raw = None if sys.stdin.isatty() else sys.stdin.buffer.read()
        piped = None if raw in (None, b"") else yield_bytes(raw)
    install = CLIInstall(name=name,
                         cli=cli,
                         config=config,
                         accessor=cli.accessor(config))
    stdout, io, _ = await handle_cli(install, [name, *argv],
                                     SessionState(session_id=name),
                                     stdin=piped)
    sys.stdout.buffer.write(await materialize(stdout))
    sys.stderr.buffer.write(await materialize(io.stderr))
    return io.exit_code


def run_cli(name: str,
            cli,
            config_model,
            config: dict[str, str],
            stdin: bool = False) -> int:
    """Entry point for one CLI's `<name>_main.py`.

    Args:
        name (str): the CLI's head word, which is also its session id.
        cli: its `CLI`.
        config_model: its pydantic config model.
        config (dict[str, str]): each config field the harness supplies,
            mapped to the environment variable carrying it.
            `cli/shims.mjs` sets those from the task's `clis:` block,
            so a task configures its CLIs in its own yaml. A mapping
            rather than one pair because `gsheet` takes five -- three
            credentials, an API base and a folder id -- where the rest
            take one.
        stdin (bool): whether the CLI reads a body from standard input.
            A body on a pipe spares a shim translating a path operand
            out of the agent's virtual filesystem.

    Returns:
        int: process exit status.
    """
    fields = {}
    for field, variable in config.items():
        value = os.environ.get(variable)
        if not value:
            sys.stderr.write(f"{name}: {variable} is not set\n")
            return 2
        fields[field] = value
    return asyncio.run(
        dispatch(name, cli, config_model(**fields), sys.argv[1:], stdin))
