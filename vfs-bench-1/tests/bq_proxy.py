"""BigQuery proxy catalog views must reflect the emulator's live tables."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.bq import proxy  # noqa: E402


class BigQueryCatalog(unittest.TestCase):

    @staticmethod
    def response(url: str) -> bytes:
        if url.endswith('/tables'):
            return json.dumps({
                'tables': [{
                    'tableReference': {
                        'projectId': 'mcp-bench0606',
                        'datasetId': 'bigquery_pricing_analysis',
                        'tableId': 'analysis',
                    },
                    'type': 'TABLE',
                }]
            }).encode()
        if url.endswith('/tables/analysis'):
            return json.dumps({
                'schema': {
                    'fields': [{
                        'name': 'Product Name',
                        'type': 'STRING',
                    }, {
                        'name': 'quantity',
                        'type': 'INTEGER',
                        'mode': 'REQUIRED',
                    }, {
                        'name': 'flags',
                        'type': 'BOOLEAN',
                        'mode': 'REPEATED',
                    }]
                }
            }).encode()
        raise AssertionError(url)

    @patch.object(proxy, 'fetch', side_effect=response)
    def test_columns_view_uses_live_rest_schema(self, fetched):
        query = ('SELECT table_name, column_name, data_type '
                 'FROM `mcp-bench0606.bigquery_pricing_analysis.'
                 'INFORMATION_SCHEMA.COLUMNS` ORDER BY ordinal_position')
        rewritten = proxy.catalog_query(query, 'http://bigquery:9050',
                                        'request-project')
        self.assertNotIn('INFORMATION_SCHEMA.COLUMNS', rewritten)
        self.assertIn('"Product Name" AS column_name', rewritten)
        self.assertIn('1 AS ordinal_position', rewritten)
        self.assertIn('"YES" AS is_nullable', rewritten)
        self.assertIn('"INT64" AS data_type', rewritten)
        self.assertIn('"NO" AS is_nullable', rewritten)
        self.assertIn('"ARRAY<BOOL>" AS data_type', rewritten)
        self.assertTrue(
            all('/projects/mcp-bench0606/' in call.args[0]
                for call in fetched.call_args_list))

    @patch.object(proxy, 'fetch', return_value=b'{"tables": []}')
    def test_empty_columns_view_is_a_typed_empty_relation(self, _fetched):
        query = ('SELECT * FROM `bigquery_pricing_analysis.'
                 'INFORMATION_SCHEMA.COLUMNS`')
        rewritten = proxy.catalog_query(query, 'http://bigquery:9050',
                                        'mcp-bench0606')
        self.assertIn('UNNEST(ARRAY<STRUCT<', rewritten)
        self.assertTrue(rewritten.endswith('>[])'))

    @patch.object(proxy, 'fetch', return_value=b'{"tables": []}')
    def test_only_from_and_join_relations_are_rewritten(self, _fetched):
        name = '`bigquery_pricing_analysis.INFORMATION_SCHEMA.COLUMNS`'
        query = f'SELECT "{name}" AS label -- FROM {name}\n'
        self.assertEqual(
            proxy.catalog_query(query, 'http://bigquery:9050',
                                'mcp-bench0606'), query)


class QueryDeadline(unittest.TestCase):
    """A query every caller has given up on is dropped, not left queued."""

    def test_the_deadline_is_upstreams_client_timeout(self):
        from server.mcp import mcp_servers
        self.assertIn(f'client_session_timeout_seconds: {proxy.DEADLINE}\n',
                      mcp_servers.upstream_config('google-cloud'))

    def test_only_queries_are_bounded(self):
        jobs = '/bigquery/v2/projects/p/jobs?prettyPrint=false'
        query = json.dumps({'configuration': {'query': {}}}).encode()
        load = json.dumps({'configuration': {'load': {}}}).encode()
        self.assertTrue(
            proxy.runs_query('POST', '/bigquery/v2/projects/p/queries', b'{}'))
        self.assertTrue(proxy.runs_query('POST', jobs, query))
        self.assertFalse(proxy.runs_query('POST', jobs, load))
        self.assertFalse(
            proxy.runs_query('GET', '/bigquery/v2/projects/p/queries/j', None))

    def test_a_query_past_the_deadline_is_dropped_as_a_timeout(self):
        # The emulator interrupts a query only when its caller hangs up,
        # and runs the next one only after that.
        import select
        import threading
        import urllib.request
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        hung_up = threading.Event()

        class Emulator(BaseHTTPRequestHandler):

            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                ready, _, _ = select.select([self.connection], [], [], 10)
                if ready and not self.connection.recv(1):
                    hung_up.set()

            def log_message(self, *_args):
                pass

        emulator = ThreadingHTTPServer(('127.0.0.1', 0), Emulator)
        front = ThreadingHTTPServer(('127.0.0.1', 0), proxy.Proxy)
        servers = (emulator, front)
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with patch.object(proxy, 'DEADLINE', 0.5), patch.object(
                    proxy.Proxy, 'upstream',
                    f'http://127.0.0.1:{emulator.server_port}'):
                request = urllib.request.Request(
                    f'http://127.0.0.1:{front.server_port}'
                    '/bigquery/v2/projects/p/queries',
                    data=b'{"query": "SELECT 1"}',
                    headers={'Content-Type': 'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(request, timeout=5)
            reply = json.loads(caught.exception.read())
            self.assertEqual(caught.exception.code, 400)
            self.assertEqual(reply['error']['errors'][0]['reason'], 'timeout')
            self.assertTrue(hung_up.wait(5))
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()


class EmulatorReplies(unittest.TestCase):
    """What the emulator leaves out of a job or a dataset comes back."""

    JOB = {
        'jobReference': {
            'jobId': 'j1',
            'projectId': 'p'
        },
        'kind': 'bigquery#job',
        'statistics': {
            'creationTime': '1790452934',
            'startTime': '1790452934',
            'endTime': '1790452935',
            'query': {
                'statementType': 'SELECT'
            }
        },
        'status': {
            'state': 'DONE'
        }
    }
    CONFIGURATION = {
        'jobType': 'QUERY',
        'query': {
            'query': 'SELECT 1',
            'useLegacySql': False
        }
    }

    def setUp(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        test = self
        self.stored = {}

        class Emulator(BaseHTTPRequestHandler):
            # Answers as goccy/bigquery-emulator 0.8.1 does: a listed job
            # has no configuration, every time is in seconds, and a
            # dataset is only its reference.

            def answer(self, document):
                payload = json.dumps(document).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                path = self.path.split('?')[0]
                if path.endswith('/jobs'):
                    self.answer({'jobs': [test.JOB]})
                elif path.endswith('/jobs/j1'):
                    self.answer({
                        **test.JOB, 'configuration': test.CONFIGURATION
                    })
                else:
                    self.answer({
                        'datasetReference': {
                            'datasetId': path.rsplit('/', 1)[1],
                            'projectId': 'p'
                        }
                    })

            def do_POST(self):
                sent = json.loads(
                    self.rfile.read(int(self.headers['Content-Length'])))
                test.stored = sent
                if self.path.split('?')[0].endswith('/jobs'):
                    self.answer({
                        **test.JOB, 'configuration': {
                            **test.CONFIGURATION, 'dryRun': True
                        }
                    })
                    return
                self.answer({'datasetReference': sent['datasetReference']})

            def do_PUT(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.answer({
                    'datasetReference': {
                        'datasetId': self.path.split('?')[0].rsplit('/', 1)[1],
                        'projectId': 'p'
                    }
                })

            do_PATCH = do_PUT

            def do_DELETE(self):
                self.send_response(204)
                self.send_header('Content-Length', '0')
                self.end_headers()

            def log_message(self, *_args):
                pass

        self.servers = (ThreadingHTTPServer(('127.0.0.1', 0), Emulator),
                        ThreadingHTTPServer(('127.0.0.1', 0), proxy.Proxy))
        for server in self.servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        patches = (patch.object(
            proxy.Proxy, 'upstream',
            f'http://127.0.0.1:{self.servers[0].server_port}'),
                   patch.object(proxy.Proxy, 'datasets',
                                proxy.DatasetRecords()))
        for patched in patches:
            patched.start()
            self.addCleanup(patched.stop)
        self.base = (f'http://127.0.0.1:{self.servers[1].server_port}'
                     '/bigquery/v2/projects/p')

    def tearDown(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()

    def call(self, path, method='GET', body=None):
        import urllib.request
        request = urllib.request.Request(
            self.base + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'},
            method=method)
        with urllib.request.urlopen(request, timeout=5) as reply:
            data = reply.read()
        return json.loads(data) if data else None

    def test_a_listed_job_has_its_configuration_and_milliseconds(self):
        # The client lists with projection=full; without a configuration it
        # builds an UnknownJob, and `created` multiplies the string.
        job = self.call('/jobs?projection=full&prettyPrint=false')['jobs'][0]
        self.assertEqual(job['configuration'], self.CONFIGURATION)
        self.assertEqual(job['statistics']['creationTime'], '1790452934000')
        self.assertEqual(job['statistics']['endTime'], '1790452935000')

    def test_a_job_has_milliseconds_and_a_minimal_listing_no_more(self):
        got = self.call('/jobs/j1')
        self.assertEqual(got['statistics']['startTime'], '1790452934000')
        listed = self.call('/jobs')['jobs'][0]
        self.assertNotIn('configuration', listed)
        self.assertEqual(listed['statistics']['creationTime'], '1790452934000')

    def test_a_query_that_scanned_nothing_says_zero_bytes(self):
        # A dry run of a statement with no rows: upstream's server divides
        # its totalBytesBilled by 1024**4, and prints totalBytesProcessed.
        dry = self.call(
            '/jobs?prettyPrint=false',
            'POST',
            body={'configuration': {
                **self.CONFIGURATION, 'dryRun': True
            }})
        for job in (dry, self.call('/jobs/j1'),
                    self.call('/jobs?projection=full')['jobs'][0]):
            statistics = job['statistics']
            self.assertEqual(statistics['totalBytesProcessed'], '0')
            self.assertEqual(statistics['query']['totalBytesProcessed'], '0')
            self.assertEqual(statistics['query']['totalBytesBilled'], '0')

    def test_counts_it_has_and_other_jobs_are_left_alone(self):
        scanned = {
            'statistics': {
                'totalBytesProcessed': '12',
                'query': {
                    'totalBytesProcessed': '12',
                    'totalBytesBilled': '12'
                }
            }
        }
        load = {'statistics': {'load': {'outputRows': '3'}}}
        before = json.loads(json.dumps([scanned, load]))
        for job in (scanned, load):
            proxy.query_bytes(job)
        self.assertEqual([scanned, load], before)

    def test_a_dataset_keeps_what_its_insert_said(self):
        # upstream's price-comparison preprocess sets both of these.
        inserted = self.call('/datasets',
                             'POST',
                             body={
                                 'datasetReference': {
                                     'datasetId': 'd',
                                     'projectId': 'p'
                                 },
                                 'description': 'Dataset for pricing',
                                 'location': 'US'
                             })
        self.assertEqual(inserted['location'], 'US')
        got = self.call('/datasets/d?prettyPrint=false')
        self.assertEqual(got['id'], 'p:d')
        self.assertEqual(got['description'], 'Dataset for pricing')
        self.assertEqual(got['location'], 'US')
        self.assertEqual(len(got['creationTime']), 13)
        self.assertEqual(got['lastModifiedTime'], got['creationTime'])
        self.call('/datasets/d', 'DELETE')
        self.assertNotIn('description', self.call('/datasets/d'))

    def test_an_update_replaces_and_a_patch_merges(self):
        self.call('/datasets',
                  'POST',
                  body={
                      'datasetReference': {
                          'datasetId': 'd',
                          'projectId': 'p'
                      },
                      'description': 'Dataset for pricing',
                      'labels': {
                          'team': 'ops',
                          'tier': 'gold'
                      }
                  })
        got = self.call('/datasets/d',
                        'PATCH',
                        body={
                            'description': None,
                            'friendlyName': 'Pricing',
                            'labels': {
                                'tier': None,
                                'region': 'us'
                            }
                        })
        self.assertNotIn('description', got)
        self.assertEqual(got['friendlyName'], 'Pricing')
        self.assertEqual(got['labels'], {'team': 'ops', 'region': 'us'})
        got = self.call('/datasets/d', 'PUT', body={'location': 'EU'})
        self.assertEqual(got['location'], 'EU')
        for gone in ('friendlyName', 'labels'):
            self.assertNotIn(gone, self.call('/datasets/d'))

    def test_a_job_lookup_that_times_out_leaves_the_listing(self):
        document = {'jobs': [dict(self.JOB)]}
        with patch.object(proxy, 'fetch', side_effect=TimeoutError):
            proxy.configure_listing(document, 'http://emulator', 'p')
        self.assertNotIn('configuration', document['jobs'][0])


if __name__ == '__main__':
    unittest.main()
