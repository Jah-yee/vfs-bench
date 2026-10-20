"""Opt-in E2B integration: real surfaces, fresh clusters, original grader."""
import asyncio
import json
import os
import re
import shlex
import sys
import tempfile
import unittest
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

REPO = Path(__file__).resolve().parents[1]
for directory in ('', 'agent', 'task', 'tests', 'server/mcp', 'server/seed'):
    sys.path.insert(0, str(REPO / directory))

import arms  # noqa: E402
import dataset  # noqa: E402
import grading  # noqa: E402
import parity  # noqa: E402
import seed_task  # noqa: E402
from workspace import Workspace, config_for  # noqa: E402

TASK = 'k8s-deployment-cleanup'


def identity(item):
    return item['metadata']['namespace'], item['metadata']['name']


def mounted(item):
    ns, name = identity(item)
    return f'/k8s/namespaces/{ns}/deployments/{name}.json'


def relevant(item):
    """Status/resourceVersion can change between reads as pods reconcile."""
    return {
        key: item['metadata'][key]
        for key in ('uid', 'name', 'namespace', 'annotations')
    }, item['spec']


async def call(session, tool, **args):
    reply = await session.call_tool(tool, args)
    text = '\n'.join(block.text for block in reply.content
                     if getattr(block, 'text', None))
    if reply.isError:
        raise AssertionError(f'{tool}: {text}')
    return text


@unittest.skipUnless(os.environ.get('E2B_API_KEY'),
                     'live test requires E2B_API_KEY')
class KubernetesTasks(unittest.IsolatedAsyncioTestCase):

    async def test_both_surfaces_pass_original_grader(self):
        dataset.use('toolathlon')
        task = dataset.local(TASK)
        sandbox_ids = []
        for arm in ('vfs', 'mcp'):
            with tempfile.TemporaryDirectory() as scratch, patch.dict(
                    os.environ, AGENT_WORKSPACE=scratch):
                work = arms.mirage_env(task)
                arms.build_workspace_dir(task)
                seed_task.seed_mail(TASK, {'id': 'mail/mitchelle75@mcp.com'})
                async with AsyncExitStack() as stack:
                    arms.open_services(task, work, stack)
                    provenance = dataset.run_provenance(TASK)
                    sandbox_ids.append(provenance['kubernetes']['sandbox_id'])
                    k8s = await parity.open_session(stack, 'k8s', task)
                    emails = await parity.open_session(stack, 'emails', task)
                    ws = Workspace.create(config_for(task))
                    stack.callback(ws.close)
                    # A raw config read must not expose cluster credentials.
                    public = yaml.safe_load(
                        Path(os.environ['KUBECONFIG']).read_text())
                    self.assertEqual(public['users'][0]['user'], {})
                    self.assertEqual(set(public['clusters'][0]['cluster']),
                                     {'server', 'insecure-skip-tls-verify'})
                    viewed = json.loads(
                        ws.execute('kubectl config view --raw -o json'))
                    self.assertTrue(
                        all(not row['user'] for row in viewed['users']))
                    mcp_config = json.loads(await
                                            call(k8s,
                                                 'kubectl_generic',
                                                 command='config',
                                                 subCommand='view',
                                                 args=['--raw', '-o', 'json']))
                    self.assertEqual(viewed, mcp_config)
                    namespaces = ws.execute('ls /k8s/namespaces').splitlines()
                    self.assertIn('dev-experimental', namespaces)
                    raw = json.loads(
                        ws.execute(
                            'kubectl get deployments -A -o json'))['items']
                    # Concurrent requests share one upstream MCP session.
                    mcp_items = await asyncio.gather(*[
                        call(k8s,
                             'kubectl_get',
                             resourceType='deployment',
                             namespace=identity(item)[0],
                             name=identity(item)[1],
                             output='json') for item in raw
                    ])
                    mcp_items = [json.loads(item) for item in mcp_items]
                    vfs_items = [
                        json.loads(ws.execute('cat ' + mounted(item)))
                        for item in raw
                    ]
                    self.assertEqual([relevant(i) for i in raw],
                                     [relevant(i) for i in mcp_items])
                    self.assertEqual([relevant(i) for i in raw],
                                     [relevant(i) for i in vfs_items])
                    items = vfs_items if arm == 'vfs' else mcp_items
                    print(f'{arm}: surfaces agree on {len(items)} objects',
                          flush=True)
                    target = next(i for i in items
                                  if identity(i)[0].startswith('dev-'))
                    ns, name = identity(target)
                    path = mounted(target)
                    await call(k8s,
                               'kubectl_scale',
                               name=name,
                               namespace=ns,
                               resourceType='deployment',
                               replicas=0)
                    self.assertEqual(
                        json.loads(ws.execute('cat ' +
                                              path))['spec']['replicas'], 0)
                    # Runtime reads must also bypass stale cache entries.
                    script = (f'import json; item=json.load(open({path!r})); '
                              'print(item["spec"]["replicas"])')
                    self.assertEqual(
                        ws.execute('python3 -c ' +
                                   shlex.quote(script)).strip(), '0')
                    restored = target['spec']['replicas']
                    ws.execute(f'kubectl scale deployment {name} -n {ns} '
                               f'--replicas={restored}')
                    self.assertEqual(
                        json.loads(await
                                   call(k8s,
                                        'kubectl_get',
                                        resourceType='deployment',
                                        name=name,
                                        namespace=ns,
                                        output='json'))['spec']['replicas'],
                        restored)
                    self.assertEqual(
                        ws.execute('python3 -c ' +
                                   shlex.quote(script)).strip(), str(restored))
                    stdin = ws.execute(f'cat {path} | kubectl apply '
                                       '--dry-run=server -f - -o json')
                    self.assertEqual(
                        json.loads(stdin)['metadata']['name'], name)
                    denied = ws.execute(f'echo invalid > {path}')
                    self.assertTrue(denied.strip(),
                                    'write to read-only mount must fail')
                    self.assertEqual(
                        json.loads(ws.execute('cat ' +
                                              path))['spec']['replicas'],
                        restored)
                    # Read the supplied PDF through the VFS runtime.
                    document = '/workspace/CS Lab Management Guidelines.pdf'
                    pdf_script = ('from pypdf import PdfReader; '
                                  f'pdf=PdfReader({document!r}); '
                                  'print("\\n".join('
                                  'p.extract_text() for p in pdf.pages))')
                    text = ws.execute('python3 -c ' + shlex.quote(pdf_script))
                    match = re.search(r'stephen_mitch\s*ell@mcp\.com', text)
                    self.assertIsNotNone(match, text[:800])
                    recipient = re.sub(r'\s+', '', match.group(0))
                    now = datetime.now(timezone.utc)
                    old = []
                    for item in items:
                        ns, name = identity(item)
                        date = item['metadata'].get(
                            'annotations', {}).get('app-version-release-date')
                        if not ns.startswith('dev-') or not date:
                            continue
                        age = (now - datetime.fromisoformat(
                            date.replace('Z', '+00:00'))).days
                        if age > 30:
                            old.append((age, ns, name))
                    old.sort(reverse=True)
                    self.assertTrue(old)
                    for age, ns, name in old:
                        if arm == 'mcp':
                            await call(k8s,
                                       'kubectl_scale',
                                       name=name,
                                       namespace=ns,
                                       resourceType='deployment',
                                       replicas=0)
                        else:
                            ws.execute(
                                f'kubectl scale deployment {name} -n {ns} '
                                '--replicas=0')
                    body = (
                        'Dear Cluster Admin,\n\nWe have cleaned up '
                        f'{len(old)} deployments running application '
                        "versions that haven't been updated in the last "
                        '30 days. We list them here in chronological order '
                        'from oldest to newest release date for your '
                        'reference:\n\n' +
                        '\n'.join(f'- {ns}/{name}: Running version released '
                                  f'{age} days ago' for age, ns, name in old) +
                        '\n\nBest,\nEmma Mitchell')
                    if arm == 'mcp':
                        await call(emails,
                                   'send_email',
                                   to=recipient,
                                   subject='Deployment cleanup',
                                   body=body)
                    else:
                        arguments = json.dumps({
                            'to': recipient,
                            'subject': 'Deployment cleanup',
                            'body': body
                        })
                        sent = ws.execute('emails send_email ' +
                                          shlex.quote(arguments))
                        self.assertEqual(
                            sent.strip(),
                            f'Email sent successfully to {recipient}')
                    self.assertEqual(grading.grade(task), 0)
                    print(f'{arm}: original cleanup/email grader PASS',
                          flush=True)
        self.assertEqual(len(set(sandbox_ids)), 2,
                         'each arm requires a new cluster')


if __name__ == '__main__':
    unittest.main()
