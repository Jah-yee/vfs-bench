"""Install the browser server and Chromium from Toolathlon's npm lock."""
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from server.mcp.npm_lock import derive as derive_lock

REPO = Path(__file__).resolve().parents[2]
VENDOR = REPO / 'vendor/browser-mcp'
PACKAGE = '@lockon0927/playwright-mcp-with-chunk'
ENTRY = VENDOR / 'node_modules' / PACKAGE / 'cli.js'


def derive():
    derive_lock(PACKAGE, VENDOR, 'toolathlon-browser-mcp')


def arguments(workdir):
    """Only substitute the workspace in the original command arguments."""
    source = subprocess.check_output([
        'git', '-C',
        str(REPO / 'submodule/Toolathlon'), 'show',
        'HEAD:configs/mcp_servers/playwright_with_chunk.yaml'
    ],
                                     text=True)
    args = yaml.safe_load(source)['params']['args']
    assert args[:2] == ['-y', PACKAGE]
    return [
        value.replace('${agent_workspace}', str(workdir)) for value in args[2:]
    ]


def options(workdir):
    """Commander option spelling for the same pinned CLI arguments."""
    args = arguments(workdir)
    result = {}
    while args:
        flag = args.pop(0)
        if not flag.startswith('--'):
            raise ValueError(f'Unexpected upstream browser argument: {flag}')
        words = flag[2:].split('-')
        negative = words[0] == 'no'
        if negative:
            words = words[1:]
        key = words[0] + ''.join(word.title() for word in words[1:])
        result[key] = (args.pop(0) if args and not args[0].startswith('--')
                       else not negative)
    return result


def image_name():
    digest = hashlib.sha256()
    for name in ('docker/browser.Dockerfile',
                 'vendor/browser-mcp/package.json',
                 'vendor/browser-mcp/package-lock.json',
                 'server/clients/browser.mjs'):
        digest.update((REPO / name).read_bytes())
    return 'toolathlon-browser:' + digest.hexdigest()[:16]


def main():
    derive()
    # Send only browser build inputs, never the checkout or development keys.
    with tempfile.TemporaryDirectory(prefix='browser-build-') as directory:
        directory = Path(directory)
        for name in ('docker/browser.Dockerfile',
                     'vendor/browser-mcp/package.json',
                     'vendor/browser-mcp/package-lock.json',
                     'server/clients/browser.mjs'):
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / name, target)
        subprocess.run([
            'docker', 'build', '--file',
            str(directory / 'docker/browser.Dockerfile'), '--tag',
            image_name(),
            str(directory)
        ],
                       check=True)


if __name__ == '__main__':
    main()
