"""Verify the Kubernetes conversion against the pinned original sources."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server.mcp.setup_kubernetes import derive  # noqa: E402


class KubernetesLineage(unittest.TestCase):

    def test_dependency_closure_is_copied_from_original_lock(self):
        with tempfile.TemporaryDirectory() as scratch:
            derive(Path(scratch))
            for name in ('package.json', 'package-lock.json'):
                self.assertEqual(
                    (Path(scratch) / name).read_bytes(),
                    (REPO / 'vendor/kubernetes-mcp' / name).read_bytes())

    def test_prompt_and_mail_config_are_original_bytes(self):
        for source, target in [('docs/task.md', 'task.md'),
                               ('emails_config.json', 'emails_config.json')]:
            original = subprocess.check_output([
                'git', '-C',
                str(REPO / 'submodule/Toolathlon'), 'show',
                'HEAD:tasks/finalpool/k8s-deployment-cleanup/' + source
            ])
            self.assertEqual(original,
                             (REPO /
                              'task/toolathlon/k8s-deployment-cleanup/shared' /
                              target).read_bytes())

    def test_both_surfaces_use_original_mail_account(self):
        task = REPO / 'task/toolathlon/k8s-deployment-cleanup'
        mail = json.loads((task / 'shared/emails_config.json').read_text())
        config = yaml.safe_load((task / 'vfs/workspace.yaml').read_text())
        names = {
            'username': 'email',
            'password': 'password',
            'imapHost': 'imap_server',
            'imapPort': 'imap_port',
            'smtpHost': 'smtp_server',
            'smtpPort': 'smtp_port',
            'useSsl': 'use_ssl'
        }
        self.assertEqual(config['mounts']['/mail']['config'], {
            key: mail[value]
            for key, value in names.items()
        })
        self.assertEqual(
            config['clis']['emails'], {
                'cli': '../../../../cli/toolathlon/emails.mjs:EMAILS',
                'config': {
                    'apiBase': '${EMAILS_CLI_URL}',
                    'timeoutMs': 120000,
                }
            })


if __name__ == '__main__':
    unittest.main()
