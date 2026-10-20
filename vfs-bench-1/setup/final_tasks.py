"""Derive final-batch task files from the pinned original configurations."""
import json
from pathlib import Path

import yaml

from server.mcp.mcp_servers import timeout_for
from server.seed.final_batch import TASKS
from server.seed.kubernetes import original
from server.seed.travel_video import TOOLS

REPO = Path(__file__).resolve().parents[1]
CLI_NAMES = {
    'google_map': ('google-map', 'MAPS'),
    'youtube': ('youtube', 'YOUTUBE'),
    'youtube-transcript': ('youtube-transcript', 'TRANSCRIPT'),
    'rail_12306': ('rail-12306', 'RAIL'),
    'memory': ('memory', 'MEMORY'),
    'yahoo-finance': ('yahoo-finance', 'YAHOO')
}


class WorkspaceDumper(yaml.SafeDumper):

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def derive():
    for task in TASKS:
        root = REPO / 'task/toolathlon' / task
        shared, vfs = root / 'shared', root / 'vfs'
        shared.mkdir(parents=True, exist_ok=True)
        vfs.mkdir(exist_ok=True)
        prefix = f'tasks/finalpool/{task}/'
        config = json.loads(original(prefix + 'task_config.json'))
        servers = config['needed_mcp_servers']
        (root / 'task.json').write_text(
            json.dumps({
                'id': 'toolathlon_' + task,
                'fixtures': []
            }, indent=2) + '\n')
        workspace = {
            'mode':
            'EXEC',
            'runtimes': [{
                'name': 'pyodide',
                'config': {
                    'packageBaseUrl': '${PYODIDE_PACKAGES}',
                    'sysPath': ['/opt/wheels/*.whl']
                }
            }, 'workspace'],
            'clis': {},
            'mounts': {
                '/work': {
                    'vfs': 'disk',
                    'config': {
                        'root': '${AGENT_WORKSPACE}'
                    }
                },
                '/tmp': {
                    'vfs': 'ram'
                },
                '/opt/wheels': {
                    'vfs': 'disk',
                    'config': {
                        'root': '${WHEELS_DIR}'
                    }
                }
            }
        }
        clis, mounts = workspace['clis'], workspace['mounts']
        instructions = []
        if 'web_search' in config['needed_local_tools']:
            clis['web-search'] = {
                'cli': '../../../../cli/toolathlon/research.mjs:SEARCH',
                'config': {
                    'apiBase': '${SEARCH_CLI_URL}'
                }
            }
            instructions.append('Use `web-search web_search` for web search.')
        if 'playwright_with_chunk' in servers:
            clis['browser'] = {
                'cli': '../../../../cli/toolathlon/browser.mjs:BROWSER',
                'config': {
                    'apiBase': '${BROWSER_URL}'
                }
            }
            instructions.append(
                'Browser commands preserve the original tool suffix: '
                '`browser_navigate` becomes `browser navigate`. Use `browser '
                '--help` to list tools.')
        if 'fetch' in servers:
            clis['fetch'] = {
                'cli': '../../../../cli/toolathlon/research.mjs:WEB',
                'config': {
                    'apiBase': '${FETCH_CLI_URL}',
                    'timeoutMs': 1000 * timeout_for('fetch')
                }
            }
            instructions.append(
                'Use `fetch fetch_html`, `fetch fetch_txt`, `fetch '
                'fetch_markdown` or `fetch fetch_json` with the original '
                '`url` and optional '
                '`headers` arguments.')
        for server in servers:
            if server in CLI_NAMES:
                name, export = CLI_NAMES[server]
                clis[name] = {
                    'cli':
                    '../../../../cli/toolathlon/travel-video.mjs:' + export,
                    'config': {
                        'apiBase': '${' + TOOLS[server][2] + '}',
                        'timeoutMs': 1000 * timeout_for(server)
                    }
                }
                instructions.append(
                    f'Use `{name} <original-tool-name>`; `{name} --help` '
                    f'lists the original tools.')
        locations = [
            'Each independent shell call starts in `/work`. Your workspace '
            'is `/work`; `/tmp` is scratch space. Use ordinary filesystem '
            'commands to inspect and edit files.',
            'Python runs in Pyodide with `python3`; use service CLIs for '
            'network operations. Installed wheels are on the import path; '
            'use `openpyxl` for spreadsheets. Run service CLIs directly in '
            'the shell; Python cannot launch OS subprocesses. Redirect CLI '
            'output to `/work` and open that file in Python for processing.'
        ]
        if 'google_sheet' in servers:
            template = yaml.safe_load(
                (REPO / 'task/toolathlon/gdp-cr5-analysis/vfs/workspace.yaml'
                 ).read_text())
            clis['google-sheet'] = template['clis']['google-sheet']
            mounts['/gd'] = template['mounts']['/gd']
            instructions.append(
                'Use `google-sheet <original-tool-name>` with one JSON '
                'argument object. For values, use `google-sheet '
                'get_sheet_data '
                '\'{"spreadsheet_id":"ID","sheet":"TAB","range":"A1:C10"}\'`. '
                'Run `google-sheet <command> --help` for the original '
                'argument schema. Read full `.gsheet.json` when grid '
                'formatting or '
                'metadata is needed.')
            locations.append(
                'The task Drive folder is mounted at `/gd`; Sheets appear as '
                '`.gsheet.json` files with worksheet data and metadata.')
        if 'arxiv_local' in servers:
            clis['arxiv-local'] = {
                'cli': '../../../../cli/toolathlon/papers.mjs:ARXIV',
                'config': {
                    'apiBase': '${ARXIV_CLI_URL}',
                    'timeoutMs': 1000 * timeout_for('arxiv_local')
                }
            }
            instructions.append(
                'Use `arxiv-local <original-tool-name>`; `arxiv-local '
                '--help` lists paper tools.')
        if 'notion' in servers:
            connection = {'apiKey': task, 'baseUrl': '${NOTION_URL}/v1'}
            clis['notion'] = {
                'cli': '../../../../cli/toolathlon/travel-video.mjs:NOTION',
                'config': {
                    'apiBase': '${NOTION_CLI_URL}',
                    'timeoutMs': 1000 * timeout_for('notion')
                }
            }
            mounts['/notion'] = {'vfs': 'notion', 'config': dict(connection)}
            instructions.append(
                'Use `notion <original-tool-name>` with one JSON argument '
                'object; `notion --help` lists the Notion tools. Pages and '
                'databases are mounted at `/notion`. Query database rows '
                'with `notion post-database-query '
                '\'{"database_id":"ID","page_size":100}\'`; '
                'mounted `page.json` also includes rendered content and '
                'blocks. Read those when the task needs them.')
        if 'emails' in servers:
            from server.seed.business_mail import config_path
            account = json.loads(original(config_path(task)))
            connection = {
                'imapHost': '127.0.0.1',
                'imapPort': '${BUSINESS_IMAP_PORT}',
                'smtpHost': '127.0.0.1',
                'smtpPort': '${BUSINESS_SMTP_PORT}',
                'username': account['email'],
                'password': account['password'],
                'useSsl': account['use_ssl']
            }
            clis['emails'] = {
                'cli': '../../../../cli/toolathlon/emails.mjs:EMAILS',
                'config': {
                    'apiBase': '${EMAILS_CLI_URL}',
                    'timeoutMs': 120000
                }
            }
            mounts['/mail'] = {'vfs': 'email', 'config': dict(connection)}
            instructions.append(
                'Mail is mounted read-only at `/mail`. Use `emails '
                '<original-tool-name> \'<JSON arguments>\'` for the pinned '
                'original email operations. IDs come from `emails` results. '
                'The mutations are `emails move_email`, `emails '
                'delete_email`, `emails move_emails` and `emails '
                'delete_emails`; use `emails --help` for '
                'the complete list and `emails <tool> --help` for the '
                'original argument schema.')
        if 'huggingface' in servers:
            clis['hf'] = {
                'cli': 'hf',
                'config': {
                    'endpoint': '${HF_ENDPOINT}',
                    'token': '${HF_TOKEN}'
                }
            }
            instructions.append(
                'Use `hf --help` for Hugging Face model, dataset and '
                'repository operations.')
        if 'github' in servers:
            clis['gh'] = {
                'cli': 'gh',
                'config': {
                    'baseUrl': '${GITHUB_URL}/api/v3',
                    'token': 'fixture'
                }
            }
            instructions.append(
                'Use `gh --help` for GitHub repository lookup and reads.')
        instructions.append(
            'Service commands accepting JSON take one argument object or '
            'piped JSON with `-`. Use `<cli> <command> --help` for the '
            'original argument schema.')
        (vfs / 'workspace.yaml').write_text(
            yaml.dump(workspace, Dumper=WorkspaceDumper, sort_keys=False))
        (vfs / 'VFS.md').write_text('\n'.join(locations) + '\n')
        (vfs / 'SKILL.md').write_text('\n\n'.join(instructions) + '\n')
        from setup.task_surfaces import upgrade
        upgrade(task)
        print(task)


if __name__ == '__main__':
    derive()
