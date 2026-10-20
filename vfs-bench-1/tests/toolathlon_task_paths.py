import sys
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from task import toolathlon  # noqa: E402

POLICY = REPO / 'task/toolathlon/task_paths.py'


class TaskPaths(unittest.TestCase):

    def test_every_workspace_runs_under_the_policy(self):
        # The hook the runner calls on each task's workspace.yaml, on two
        # tasks whose mounts differ: `node --test
        # tests/toolathlon_task_paths.mjs` checks what that file refuses.
        for task in ('music-analysis', 'sync-todo-to-readme'):
            with self.subTest(task=task):
                body = yaml.safe_load((REPO / 'task/toolathlon' / task /
                                       'vfs/workspace.yaml').read_text())
                toolathlon.workspace_config(body)
                default = body['profiles']['default']
                program = [{'script': str(POLICY), 'runtime': 'monty'}]
                self.assertEqual(default['policy'], {
                    'pre_execute': program,
                    'pre_command': program
                })
                self.assertTrue(POLICY.is_file())
                self.assertEqual(default['cwd'], '/workspace')

    def test_a_refusal_says_why(self):
        output = toolathlon.shell_output('music-analysis', 'find /', '',
                                         'find: Permission denied\n')
        self.assertEqual(
            output, 'find: Permission denied\npolicy denied: '
            f'{toolathlon.REFUSED_PATH}')

    def test_other_errors_answer_as_the_shell_does(self):
        # A file's own permission error names the file; only the policy's
        # refusal is the bare `<command>: Permission denied`.
        stderr = 'cat: /gd/sheet.json: Permission denied\n'
        self.assertEqual(
            toolathlon.shell_output('music-analysis', 'cat /gd/sheet.json', '',
                                    stderr), stderr)


if __name__ == '__main__':
    unittest.main()
