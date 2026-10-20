"""google-cloud file arguments follow the task's workspace root."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
for directory in ('', 'agent'):
    sys.path.insert(0, str(REPO / directory))

from server.clients.original_tools import (  # noqa: E402
    cloud_workspace_request, cloud_workspace_response)


class CloudPaths(unittest.TestCase):

    def test_file_arguments_and_replies_use_the_virtual_root(self):
        for root in ('/work', '/workspace'):
            with (self.subTest(root=root), tempfile.TemporaryDirectory() as
                  tmp):
                work = Path(tmp).resolve()
                request = cloud_workspace_request(
                    {
                        'name': 'storage_upload_file',
                        'arguments': {
                            'bucket_name': 'b',
                            'source_file_path': root + '/report.csv',
                            'destination_blob_name': 'report.csv'
                        }
                    }, work, root)
                self.assertEqual(request['arguments']['source_file_path'],
                                 str(work / 'report.csv'))
                for path in ('/etc/passwd', root + '/../secret'):
                    with self.assertRaises(ValueError):
                        cloud_workspace_request(
                            {
                                'name': 'bigquery_load_csv_data',
                                'arguments': {
                                    'csv_file_path': path
                                }
                            }, work, root)
                query = {
                    'name': 'bigquery_run_query',
                    'arguments': {
                        'query': 'SELECT "' + root + '/x"'
                    }
                }
                self.assertIs(cloud_workspace_request(query, work, root),
                              query)
                reply = {
                    'content': [{
                        'type': 'text',
                        'text': f'Downloaded to {work}/report.csv'
                    }]
                }
                cloud_workspace_response('storage_download_file', reply, work,
                                         root)
                self.assertEqual(reply['content'][0]['text'],
                                 f'Downloaded to {root}/report.csv')


class BusinessCloudServices(unittest.TestCase):
    """woocommerce-new-welcome's box serves everything its tools reach.

    Its BigQuery lives in the E2B box, and its Cloud Storage and Cloud
    Logging used to be whatever the host stack had up: nothing, on a stack
    whose draws had all been E2B tasks, so `storage-list-buckets` retried a
    refused connection past the CLI's 30 s and `logging-list-logs` was
    refused outright.
    """

    TUNNELS = {9051: 31051, 9061: 31061, 9110: 31110, 4443: 31443}

    def test_both_arms_reach_the_box_and_the_proxy(self):
        import dataset

        from server.mcp.mcp_servers import Launch, google_cloud
        from server.seed import business, business_bigquery

        box = SimpleNamespace(sandbox_id='google-cloud-services-test',
                              written={},
                              background=[])
        box.files = SimpleNamespace(write=lambda path, data, user=None: box.
                                    written.update({path: data}))
        box.commands = SimpleNamespace(
            run=lambda line, **_kwargs: box.background.append(line))
        ran = []
        task = 'woocommerce-new-welcome'
        key = REPO / f'state/business/{box.sandbox_id}-gcp.json'
        self.addCleanup(key.unlink, missing_ok=True)
        with tempfile.TemporaryDirectory() as work, patch.dict(
                os.environ), patch.object(
                    business_bigquery,
                    'command',
                    side_effect=lambda _box, line, **_kwargs: ran.append(line)
                ), patch.object(
                    business,
                    'expose',
                    side_effect=lambda _box, port, *_args: self.TUNNELS[port]):
            business_bigquery.start(box, None)
            dataset.use('toolathlon')
            env = google_cloud(Launch(dataset.local(task), work))['env']

        self.assertEqual(env['BIGQUERY_EMULATOR_HOST'],
                         'http://127.0.0.1:31051')
        self.assertEqual(env['STORAGE_EMULATOR_HOST'],
                         'http://127.0.0.1:31443')
        self.assertEqual(env['CLOUD_LOGGING_API'],
                         f'http://127.0.0.1:31110/api/{task}/logging')
        # compose's Cloud Storage fake, naming the tunnel as its address,
        # and reachable from the emulator by compose's name for it.
        gcs, = (line for line in ran if '--name task-gcs' in line)
        self.assertIn(business_bigquery.storage_args(31443)[0], gcs)
        self.assertIn('-external-url http://127.0.0.1:31443', gcs)
        self.assertIn('--network-alias gcs', gcs)
        emulator, = (line for line in ran if '--name task-bigquery' in line)
        self.assertIn('--env STORAGE_EMULATOR_HOST=http://gcs:4443', emulator)
        # The proxy and the fixture API are this checkout's own files, run
        # the way `docker/service.sh` runs them.
        for path in business_bigquery.RUNTIME:
            self.assertEqual(box.written['/opt/fixture-api/' + path],
                             (REPO / path).read_bytes())
        self.assertTrue(
            any('-m server.bq.proxy --listen 9051 --upstream 9050' in line
                for line in box.background))
        self.assertTrue(
            any('uvicorn app:app' in line and '--port 9110' in line
                for line in box.background))


if __name__ == '__main__':
    unittest.main()
