"""Opt-in transport/grader checks for the three original Kubernetes tasks.

Golden CSVs are test oracles only; they are never seeded into an agent run.
These checks establish capability and grader connectivity, not model scores.
"""
import json
import os
import shlex
import sys
import tempfile
import traceback
import unittest
from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
for directory in ('', 'agent', 'task', 'tests', 'server/mcp'):
    sys.path.insert(0, str(REPO / directory))

import arms  # noqa: E402
import dataset  # noqa: E402
import grading  # noqa: E402
import parity  # noqa: E402
from kubernetes_tasks import call  # noqa: E402
from workspace import Workspace, config_for  # noqa: E402

from server.clients import gws  # noqa: E402
from server.seed.kubernetes import original  # noqa: E402


async def check_pod_exec(mcp):
    """Exercise client-node's WebSocket path through the E2B proxy."""
    result = await call(mcp,
                        'exec_in_pod',
                        name='mysql-f1-0',
                        namespace='data',
                        container='mysql',
                        command=['printf', 'mcp-exec-ready'])
    if result.strip() != 'mcp-exec-ready':
        raise AssertionError(f'Unexpected pod exec output: {result!r}')


@unittest.skipUnless(os.environ.get('E2B_API_KEY'),
                     'live test requires E2B_API_KEY')
class KubernetesExtended(unittest.IsolatedAsyncioTestCase):

    async def run_task(self, name, exercise):
        dataset.use('toolathlon')
        task = dataset.local(name)
        with tempfile.TemporaryDirectory() as work, patch.dict(
                os.environ, AGENT_WORKSPACE=work):
            arms.mirage_env(task)
            arms.build_workspace_dir(task)
            async with AsyncExitStack() as stack:
                arms.open_services(task, work, stack)
                mcp = await parity.open_session(stack, 'k8s', task)
                stack.callback(dataset.close_commands, name)
                ws = Workspace.create(config_for(task))
                stack.callback(ws.close)
                try:
                    await exercise(ws, mcp, Path(work))
                except BaseException:
                    traceback.print_exc()
                    raise
                self.assertEqual(grading.grade(task), 0)
                print(name + ': native MCP + VFS + original grader PASS',
                      flush=True)

    async def test_mysql(self):

        async def exercise(ws, mcp, work):
            await check_pod_exec(mcp)
            # Both surfaces must keep their own command alive after returning.
            ready = ws.execute(
                'kubectl port-forward -n data service/mysql-f1 30124:3306')
            self.assertIn('Forwarding from', ready)
            await call(mcp,
                       'port_forward',
                       resourceType='service',
                       resourceName='mysql-f1',
                       namespace='data',
                       localPort=30125,
                       targetPort=3306)
            print('Both forwards ready', flush=True)
            for port in (30124, 30125):
                args = (f'mysql -h 127.0.0.1 -P {port} '
                        '-u reader -pmcpbench0606 f1')
                self.assertEqual(
                    ws.execute_result(
                        args + " -e 'SELECT COUNT(*) FROM races'")['stdout'],
                    'COUNT(*)\n1125\n')
                self.assertIn(
                    'ERROR 1142',
                    ws.execute(args + " -e 'CREATE TABLE forbidden (id INT)'"))
            # The real client runs each statement of one -e in turn.
            self.assertEqual(
                ws.execute_result(
                    'mysql --protocol=TCP -h localhost -P 30124 -u reader '
                    "-pmcpbench0606 f1 -e 'SELECT 1; SELECT 2'")['stdout'],
                '1\n1\n2\n2\n')
            for number in (1, 2):
                data = original(
                    'tasks/finalpool/k8s-mysql/groundtruth_workspace/'
                    f'gtq{number}.csv').decode()
                ws.execute('printf %s ' + shlex.quote(data) +
                           f' > /workspace/results_{number}.csv')
            for template in work.glob('*.csv'):
                if template.name not in {'results_1.csv', 'results_2.csv'}:
                    ws.execute('rm /workspace/' + template.name)

        await self.run_task('k8s-mysql', exercise)

    async def test_redis(self):

        async def exercise(ws, mcp, work):
            releases = json.loads(ws.execute('helm list -A -o json'))
            self.assertEqual(releases[0]['chart'], 'redis-19.0.0')
            # Native Helm is required: the original MCP upgrade schema has no
            # chart-version field. Do not add one to the measured MCP schema.
            result = ws.execute(
                'helm upgrade redis bitnami/redis --version 22.0.0 '
                '-n shared-services -f /workspace/config/redis-values.yaml '
                '--set image.repository=bitnamilegacy/redis '
                '--set global.security.allowInsecureImages=true '
                '--wait --timeout 10m')
            self.assertIn('has been upgraded', result)
            pods = json.loads(await call(mcp,
                                         'kubectl_get',
                                         resourceType='pods',
                                         namespace='shared-services',
                                         output='json'))['items']
            self.assertEqual(len(pods), 3)
            self.assertTrue(all(p['status'] == 'Running' for p in pods))

        await self.run_task('k8s-redis-helm-upgrade', exercise)

    async def test_safety_audit(self):

        async def exercise(ws, mcp, work):
            pods = json.loads(await call(mcp,
                                         'kubectl_get',
                                         resourceType='pods',
                                         allNamespaces=True,
                                         output='json'))['items']
            sensitive = {
                'SYS_ADMIN', 'SYS_MODULE', 'SYS_PTRACE', 'NET_ADMIN',
                'SYS_TIME', 'SYS_BOOT'
            }
            rows = []
            for summary in pods:
                ns = summary['namespace']
                if ns not in {'production', 'dev', 'staging', 'test'}:
                    continue
                pod = json.loads(await call(mcp,
                                            'kubectl_get',
                                            resourceType='pod',
                                            name=summary['name'],
                                            namespace=ns,
                                            output='json'))
                spec = pod['spec']
                volumes = {
                    v['name']: v.get('hostPath', {}).get('path', '')
                    for v in spec.get('volumes', [])
                }
                for c in spec['containers']:
                    sc = {
                        **spec.get('securityContext', {}),
                        **c.get('securityContext', {})
                    }
                    privileged = sc.get('privileged', False)
                    capabilities = {
                        s.removeprefix('CAP_')
                        for s in sc.get('capabilities', {}).get('add', [])
                    }
                    score = min(6, len(capabilities & sensitive) * 4)
                    paths = [
                        volumes[m['name']] for m in c.get('volumeMounts', [])
                    ]
                    score += (5
                              if '/var/run/docker.sock' in paths else 3 if any(
                                  p in {
                                      '/etc', '/root', '/proc', '/sys',
                                      '/var/lib/kubelet', '/var/run/containerd'
                                  } for p in paths) else 0)
                    score += 2 * sum(
                        bool(spec.get(k))
                        for k in ('hostNetwork', 'hostPID', 'hostIPC'))
                    score += 2 * bool(sc.get('allowPrivilegeEscalation'))
                    score += 2 * (sc.get('runAsUser') == 0
                                  or sc.get('runAsNonRoot') is False)
                    score += int(
                        sc.get('readOnlyRootFilesystem', False) is False)
                    score = 10 if privileged else min(10, score)
                    rows.append([
                        ns, pod['metadata']['name'], c['name'],
                        str(privileged).lower(), c['image'],
                        pod['metadata']['creationTimestamp'], spec['nodeName'],
                        score, 'High'
                        if score >= 8 else 'Medium' if score >= 4 else 'Low'
                    ])
            self.assertEqual(len(rows), 10)
            sheet = gws.find('Kubernetes Security Audit')[0]['id']
            path = '/gd/K8sSafetyAudit/Kubernetes Security Audit.gsheet.json'
            document = json.loads(ws.execute('cat ' + shlex.quote(path)))
            self.assertEqual(document['spreadsheetId'], sheet)
            async with AsyncExitStack() as stack:
                sheets = await parity.open_session(
                    stack, 'google_sheet', dataset.local('k8s-safety-audit'))
                before = json.loads(await call(sheets,
                                               'get_sheet_data',
                                               spreadsheet_id=sheet,
                                               sheet='Week1',
                                               range='A1:I20'))
                self.assertEqual(before['valueRanges'][0]['values'],
                                 gws.read_values(sheet, 'Week1!A1:I20'))
                grid = json.loads(await call(sheets,
                                             'get_sheet_data',
                                             spreadsheet_id=sheet,
                                             sheet='Week1',
                                             range='A1:I2',
                                             include_grid_data=True))
                header = grid['sheets'][0]['data'][0]['rowData'][0]['values'][
                    0]
                style = header['userEnteredFormat']
                self.assertTrue(style['textFormat']['bold'])
                self.assertTrue(
                    all(style['borders'][edge]['style'] == 'SOLID'
                        for edge in ('top', 'bottom', 'left', 'right')))
                await call(sheets,
                           'update_cells',
                           spreadsheet_id=sheet,
                           sheet='Week3',
                           range='A2:I2',
                           data=rows[:1])
                output = ws.execute('sheets update_cells ' + shlex.quote(
                    json.dumps({
                        'spreadsheet_id': sheet,
                        'sheet': 'Week3',
                        'range': 'A3',
                        'data': rows[1:]
                    })))
                print('Sheets write:', output[:300], flush=True)
                after = json.loads(await call(sheets,
                                              'get_sheet_data',
                                              spreadsheet_id=sheet,
                                              sheet='Week3',
                                              range='A1:I20'))
                values = gws.read_values(sheet, 'Week3!A1:I20')
                self.assertEqual(len(values), 11)
                self.assertEqual(after['valueRanges'][0]['values'], values)

        await self.run_task('k8s-safety-audit', exercise)


if __name__ == '__main__':
    unittest.main()
