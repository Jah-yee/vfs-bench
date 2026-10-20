"""Every tool CLI's SKILL.md section lists the tools its server advertises."""
import json
import re
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from setup import task_surfaces  # noqa: E402
from task import mcpatlas  # noqa: E402

TASKS = REPO / 'task/toolathlon'
ATLAS = REPO / 'task/mcpatlas'
# Toolathlon's words for a workspace with no interpreter, which every Atlas
# task whose MCP arm has none says too.
NO_RUNTIMES = ('Python (`python` or `python3`), Perl, JavaScript/Node.js, '
               'and TypeScript\nruntimes are unavailable. Use the shell '
               'commands and task CLIs documented\nbelow; do not probe for '
               'or attempt to install other runtimes.')


def numbered(value):
    """The arguments with each '#NAME' placeholder a number."""
    if isinstance(value, dict):
        return {key: numbered(item) for key, item in value.items()}
    if isinstance(value, list):
        return [numbered(item) for item in value]
    if isinstance(value, str) and value.startswith('#'):
        return 0
    return value


class SkillTables(unittest.TestCase):

    def test_every_tool_cli_has_the_rendered_section(self):
        catalog = json.loads(task_surfaces.CLI_TOOLS.read_text())
        for config in sorted(TASKS.glob('*/vfs/workspace.yaml')):
            task = config.parts[-3]
            skill = (config.parent / 'SKILL.md').read_text()
            clis = (yaml.safe_load(config.read_text()) or {}).get('clis') or {}
            for cli in clis:
                if cli in task_surfaces.NATIVE:
                    continue
                with self.subTest(task=task, cli=cli):
                    self.assertIn(cli, catalog)
                    self.assertIn(
                        f'## {cli}\n\n{task_surfaces.tool_section(cli)}\n',
                        skill)

    def test_code_examples_keep_their_line_breaks(self):
        # W&B's GraphQL examples carry `# ...` comments; folded onto one
        # line, a comment swallowed the fields and braces after it.
        self.assertEqual(
            task_surfaces.prose('Use:\n```graphql\nruns {  # or files\n'
                                '    id\n}\n```\nthen   page.'),
            'Use: ```graphql<br>runs {  # or files<br>    id<br>}<br>``` '
            'then page.')
        self.assertIn('# Use run(name: ...) with the Run ID<br>',
                      task_surfaces.tool_section('wandb'))

    def test_map_values_show_their_fields(self):
        # notion create-a-database maps each property's name to an object
        # that requires `title`, as MCP's schema says.
        tool = next(tool for tool in json.loads(
            task_surfaces.CLI_TOOLS.read_text())['notion']
                    if tool['command'] == 'create-a-database')
        schema = tool['inputSchema']
        self.assertIn(
            'properties: dict[str, {title: dict, description?: str}]',
            task_surfaces.signature(schema, schema.get('$defs', {})))

    def test_every_web_search_task_has_the_cli(self):
        # course-schedule's prompt named `web-search web_search` while its
        # workspace had no such command.
        for config in sorted(TASKS.glob('*/vfs/workspace.yaml')):
            task = config.parts[-3]
            clis = (yaml.safe_load(config.read_text()) or {}).get('clis') or {}
            with self.subTest(task=task):
                self.assertEqual(
                    'web-search' in clis, 'web_search'
                    in task_surfaces.needed_local_tools(task))

    def test_git_is_given_where_upstream_gives_it(self):
        # 42 tasks whose model had `git` through upstream's terminal got no
        # `git` here. Against upstream's own allowlist, not the generator's
        # rule; k8s-pr-preview-testing's sandbox already runs git natively
        # (server/seed/kubernetes.py passes `browser` for it alone).
        from server.mcp.mcp_servers import upstream_config
        from server.shared_workspace import BROWSER_CAPTURES
        env = yaml.safe_load(upstream_config('terminal'))['params']['env']
        allowed = [word.strip() for word in env['ALLOWED_COMMANDS'].split(',')]
        captured = ('k8s-pr-preview-testing'
                    if 'git' in BROWSER_CAPTURES else None)
        for config in sorted(TASKS.glob('*/vfs/workspace.yaml')):
            task = config.parts[-3]
            clis = (yaml.safe_load(config.read_text()) or {}).get('clis') or {}
            skill = (config.parent / 'SKILL.md').read_text()
            servers = task_surfaces.needed_mcp_servers(task)
            given = 'git' in servers or ('terminal' in servers
                                         and 'git' in allowed
                                         and task != captured)
            with self.subTest(task=task):
                self.assertEqual('git' in clis, given)
                self.assertEqual('\n## git\n' in skill, given)

    def test_curl_is_listed_where_it_reaches_the_network(self):
        # Against the runtime's own decision, which the daemon's network
        # hook follows, so the generator's copy cannot drift from it.
        sys.path.insert(0, str(REPO / 'agent'))
        import arms
        import dataset
        dataset.use('toolathlon')
        for skill in sorted(TASKS.glob('*/vfs/SKILL.md')):
            task = skill.parts[-3]
            public = arms.public_network(TASKS / task)
            with self.subTest(task=task):
                self.assertEqual('  unzip  curl\n' in skill.read_text(),
                                 public)
                self.assertEqual(task_surfaces.upstream_network(task), public)


class AtlasSkillTables(unittest.TestCase):

    def test_every_tool_cli_has_the_rendered_section(self):
        catalog = json.loads(task_surfaces.ATLAS_CLI_TOOLS.read_text())
        for config in sorted(ATLAS.glob('*/vfs/workspace.yaml')):
            task = config.parts[-3]
            skill = (config.parent / 'SKILL.md').read_text()
            spec = yaml.safe_load(config.read_text()) or {}
            clis = [
                cli for cli in spec.get('clis') or {}
                if cli in task_surfaces.ATLAS_TOOL_COMMANDS
            ]
            python = ['python3'] if 'pyodide' in spec.get('runtimes',
                                                          []) else []
            with self.subTest(task=task):
                self.assertEqual(sorted(clis), sorted(catalog.get(task, {})))
                # Every section is one this task has, once and in order, so
                # a stale or repeated one cannot pass beside the right one.
                self.assertEqual(re.findall(r'^## (.+)$', skill, re.M),
                                 clis + python)
            for cli in clis:
                with self.subTest(task=task, cli=cli):
                    self.assertIn(
                        f'## {cli}\n\n'
                        f'{task_surfaces.atlas_tool_section(task, cli)}\n',
                        skill)

    def test_each_cli_lists_the_tools_atlas_enables(self):
        catalog = json.loads(task_surfaces.ATLAS_CLI_TOOLS.read_text())
        for task, clis in catalog.items():
            enabled = json.loads(
                (ATLAS / task /
                 'shared/atlas.json').read_text())['enabled_tools']
            for cli, tools in clis.items():
                prefix = task_surfaces.ATLAS_PREFIXES.get(cli, '')
                # Less the prefix, a tool's underscores are hyphens:
                # `wikipedia_search_wikipedia` is `wikipedia search-wikipedia`.
                with self.subTest(task=task, cli=cli):
                    self.assertEqual(
                        sorted(tool['command'] for tool in tools),
                        sorted(
                            name.split('_', 1)[1].removeprefix(prefix).replace(
                                '_', '-') for name in enabled
                            if name.split('_', 1)[0] == cli))

    def test_examples_are_valid_calls(self):
        schemas = {
            (cli, tool['command']): tool['inputSchema']
            for clis in json.loads(
                task_surfaces.ATLAS_CLI_TOOLS.read_text()).values()
            for cli, tools in clis.items()
            for tool in tools
        }
        calls = {
            (cli, command): arguments
            for cli, listed in task_surfaces.ATLAS_EXAMPLES.items()
            for command, arguments in listed
        }
        # Every listed tool has one, less the post upstream refuses.
        self.assertEqual(
            set(schemas) - set(calls),
            {('slack', 'conversations-add-message')})
        self.assertLessEqual(set(calls), set(schemas))
        for (cli, command), arguments in calls.items():
            with self.subTest(cli=cli, command=command):
                jsonschema.validate(numbered(arguments), schemas[cli, command])

    def test_skill_md_says_when_there_is_no_interpreter(self):
        for config in sorted(ATLAS.glob('*/vfs/workspace.yaml')):
            runtimes = (yaml.safe_load(config.read_text())
                        or {}).get('runtimes')
            skill = (config.parent / 'SKILL.md').read_text()
            with self.subTest(task=config.parts[-3]):
                self.assertEqual(NO_RUNTIMES in skill,
                                 runtimes == ['workspace'])


class AtlasMounts(unittest.TestCase):

    def test_every_workspace_runs_under_whole_mount(self):
        # Rebased against the yaml's directory, as agent/workspace.py's
        # `resolved` rebases it before the daemon sees it.
        from mirage.config import _absolutize_scripts
        for config in sorted(ATLAS.glob('*/vfs/workspace.yaml')):
            body = yaml.safe_load(config.read_text()) or {}
            _absolutize_scripts(body, config.resolve().parent)
            policy = body.get('profiles', {}).get('default', {}).get('policy')
            with self.subTest(task=config.parts[-3]):
                self.assertEqual(set(policy), {'pre_execute', 'pre_command'})
                for programs in policy.values():
                    self.assertEqual(len(programs), 1)
                    self.assertEqual(programs[0]['runtime'], 'monty')
                    self.assertEqual(
                        Path(programs[0]['script']).resolve(),
                        (ATLAS / 'whole_mount.py').resolve())

    def test_every_workspace_matches_characters_as_upstream(self):
        # Upstream's servers start with HOME and PATH alone; their Python
        # coerces that to LC_CTYPE=C.UTF-8, and mirage's grep, sed and expr
        # match bytes without a UTF-8 locale.
        for config in sorted(ATLAS.glob('*/vfs/workspace.yaml')):
            env = (yaml.safe_load(config.read_text()) or {}).get('env')
            with self.subTest(task=config.parts[-3]):
                self.assertEqual(env, {'LC_CTYPE': 'C.UTF-8'})

    def test_the_mounts_are_what_the_enabled_tools_read(self):
        # Both ways: a mount the tools cannot read is a way to the answer
        # the MCP arm never had, and one they can that is missing is data
        # it has and this arm lacks.
        services = [
            mount for mount in mcpatlas.MOUNT_READERS
            if not mount.startswith('/data')
        ]
        for config in sorted(ATLAS.glob('*/vfs/workspace.yaml')):
            task = config.parts[-3]
            mounts = (yaml.safe_load(config.read_text()) or {}).get('mounts')
            expected = {'/tmp'} | {
                mount
                for mount in services if mcpatlas.readable(task, mount)
            }
            if mcpatlas.readable(task, '/data'):
                expected.add('/data')
            elif mcpatlas.readable(task, '/data/repos'):
                # A repository alone is what git reads of /data.
                expected.update(mcpatlas.clones())
            with self.subTest(task=task):
                self.assertEqual(set(mounts or {}), expected)

    def test_vfs_md_lists_the_mounts(self):
        for config in sorted(ATLAS.glob('*/vfs/workspace.yaml')):
            task = config.parts[-3]
            mounts = (yaml.safe_load(config.read_text()) or {}).get('mounts')
            listed = {
                '/data/repos' if path.startswith('/data/repos/') else path
                for path in mounts or {}
            }
            vfs = (config.parent / 'VFS.md').read_text()
            with self.subTest(task=task):
                self.assertEqual(
                    set(re.findall(r'^\| `(/[^`]+)` \|', vfs, re.M)), listed)


if __name__ == '__main__':
    unittest.main()
