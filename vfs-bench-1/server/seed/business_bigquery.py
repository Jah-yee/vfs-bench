"""Owned BigQuery emulator for the original WooCommerce welcome seed."""
import gzip
import hashlib
import json
import os
import shlex
from pathlib import Path

import yaml

from server.bq.token_stub import DEFAULT_PROJECT, write_key
from server.seed.kubernetes import command

REPO = Path(__file__).resolve().parents[2]
PROJECT = DEFAULT_PROJECT
REDIRECT = ('env PYTHONPATH=/opt/fixture-bigquery '
            'BIGQUERY_EMULATOR_HOST=http://127.0.0.1:9050 ')

INPUTS = ('server/bq/token_stub.py', 'redirect/bigquery/sitecustomize.py')
# The rest of what the task's google-cloud server reaches, run in the box
# the way the stack runs it beside its own emulator (`docker/service.sh`):
# the proxy in front of the emulator, and the fixture API that is Cloud
# Logging. Left to the host they were whatever another task's stack had up,
# or nothing. Not in `sources`, which a capture must match: neither shapes
# the rows a capture holds.
RUNTIME = ('server/bq/proxy.py', 'server/api/app.py',
           'server/api/logging_store.py')
# compose's spelling of the port Cloud Storage is published on, which the
# fake writes into every location it hands back.
GCS_PUBLISHED = '${GCS_PORT:-9070}'


def storage_args(port):
    """compose's Cloud Storage fake, published on `port`.

    Args:
        port (int): where the host reaches it, which is the tunnel's port.

    Returns:
        list[str]: the pinned image and its arguments, for `docker run`.
    """
    service = yaml.safe_load(
        (REPO / 'docker/compose.yml').read_text())['services']['gcs']
    if '@sha256:' not in service['image']:
        raise ValueError('The Cloud Storage fake must be digest-pinned')
    if GCS_PUBLISHED not in service['command']:
        raise ValueError('compose no longer names where Cloud Storage is '
                         'published')
    return [
        service['image'],
        *service['command'].replace(GCS_PUBLISHED, str(port)).split()
    ]


def sources(inputs=None):
    """What `start` records, and what a restored capture must match.

    Args:
        inputs (dict | None): the bytes `start` copies into the sandbox, by
            path, so the hashes are of exactly those; read here otherwise.
    """
    if inputs is None:
        inputs = {path: (REPO / path).read_bytes() for path in INPUTS}
    compose = (REPO / 'docker/compose.yml').read_bytes()
    return {
        'image': yaml.safe_load(compose)['services']['bigquery']['image'],
        'project': PROJECT,
        'inputs_sha256': {
            path: hashlib.sha256(data).hexdigest()
            for path, data in inputs.items()
        },
        'compose_sha256': hashlib.sha256(compose).hexdigest()
    }


def same_sources(captured, current):
    """Every field `sources` records must match the capture's.

    A capture keeps its `revalidations` beside those fields, as the Sheets
    and Forms records do, and they are not a source.
    """
    return bool(captured) and all(
        captured.get(key) == value for key, value in current.items())


def start(box, stack):
    from server.seed.business import expose
    inputs = {path: (REPO / path).read_bytes() for path in INPUTS}
    record = sources(inputs)
    image = record['image']
    if '@sha256:' not in image:
        raise ValueError('The BigQuery emulator must be digest-pinned')
    # One network, as compose's: the emulator reaches Cloud Storage by the
    # service name compose gives it, which is how an extract job uploads.
    emulator = yaml.safe_load(
        (REPO / 'docker/compose.yml').read_text())['services']['bigquery']
    command(box, 'sudo docker network create task-gcp')
    command(box,
            shlex.join([
                'sudo', 'docker', 'run', '-d', '--name', 'task-bigquery',
                '--network', 'task-gcp', '-p', '127.0.0.1:9050:9050', *[
                    part for key, value in emulator['environment'].items()
                    for part in ('--env', key + '=' + value)
                ], image, '--project=' + PROJECT, '--port=9050'
            ]),
            timeout=300)
    # The tunnel before the fake, which names its published address in
    # the locations it hands back and has to be told that address.
    storage_port = expose(box, 4443, 0, 8090, stack)
    command(box,
            shlex.join([
                'sudo', 'docker', 'run', '-d', '--name', 'task-gcs',
                '--network', 'task-gcp', '--network-alias', 'gcs', '-p',
                '127.0.0.1:4443:4443', *storage_args(storage_port)
            ]),
            timeout=300)
    for path, data in inputs.items():
        target = ('/opt/fixture-api/' + path if path.startswith('server/') else
                  '/opt/fixture-bigquery/sitecustomize.py')
        box.files.write(target, data, user='root')
    for path in RUNTIME:
        box.files.write('/opt/fixture-api/' + path, (REPO / path).read_bytes(),
                        user='root')
    local = REPO / f'state/business/{box.sandbox_id}-gcp.json'
    write_key(local, PROJECT, 9061)
    box.files.write('/opt/toolathlon/configs/gcp-service_account.keys.json',
                    local.read_bytes(),
                    user='root')
    program = ('from http.server import HTTPServer; '
               'from server.bq.token_stub import TokenStub; '
               'HTTPServer(("127.0.0.1",9061),TokenStub).serve_forever()')
    box.commands.run('cd /opt/fixture-api && sudo python3 -c ' +
                     shlex.quote(program) + ' > /tmp/task-token.log 2>&1',
                     background=True,
                     timeout=0)
    command(
        box, 'for i in $(seq 1 60); do curl -fsS '
        f'http://127.0.0.1:9050/bigquery/v2/projects/{PROJECT}/datasets '
        '>/dev/null && exit 0; sleep 1; done; '
        'sudo docker logs task-bigquery; exit 1')
    # `docker/service.sh`'s bqproxy and api, on the box's loopback.
    box.commands.run(
        'cd /opt/fixture-api && sudo python3 -m server.bq.proxy '
        '--listen 9051 --upstream 9050 '
        '--storage http://127.0.0.1:4443 '
        '> /tmp/task-bqproxy.log 2>&1',
        background=True,
        timeout=0)
    box.commands.run(
        'cd /opt/fixture-api && sudo env '
        'CLOUD_LOGGING_ROOT=/tmp/cloud_logging python3 -m uvicorn '
        'app:app --app-dir /opt/fixture-api/server/api '
        '--host 127.0.0.1 --port 9110 --log-level warning '
        '> /tmp/task-logging.log 2>&1',
        background=True,
        timeout=0)
    command(
        box, 'for i in $(seq 1 60); do curl -fsS '
        f'http://127.0.0.1:9051/bigquery/v2/projects/{PROJECT}/datasets '
        '>/dev/null && curl -fsS '
        f'"http://127.0.0.1:4443/storage/v1/b?project={PROJECT}" '
        '>/dev/null && curl -fsS http://127.0.0.1:9110/healthz >/dev/null '
        '&& exit 0; sleep 1; done; sudo docker logs task-gcs; '
        'cat /tmp/task-bqproxy.log /tmp/task-logging.log; exit 1')
    api_port = expose(box, 9051, 0, 8088, stack)
    token_port = expose(box, 9061, 0, 8089, stack)
    logging_port = expose(box, 9110, 0, 8091, stack)
    account = json.loads(local.read_text())
    account['token_uri'] = f'http://127.0.0.1:{token_port}/token'
    local.write_text(json.dumps(account))
    # `API_URL` rather than the endpoint: `services.logging_api` composes
    # the task's own logging base from it, for either arm's launch.
    os.environ.update(BQ_ENDPOINT=f'http://127.0.0.1:{api_port}',
                      BIGQUERY_EMULATOR_HOST=f'http://127.0.0.1:{api_port}',
                      BQ_PROJECT=PROJECT,
                      GCP_SERVICE_ACCOUNT=str(local),
                      STORAGE_EMULATOR_HOST=f'http://127.0.0.1:{storage_port}',
                      API_URL=f'http://127.0.0.1:{logging_port}')
    return record


def state(box):
    """Capture every customer row through the same native SDK as upstream."""
    program = '''import json,datetime,decimal
from google.cloud import bigquery
from google.auth.credentials import AnonymousCredentials
client=bigquery.Client(project=PROJECT, credentials=AnonymousCredentials())
name=PROJECT+'.woocommerce_crm.customers'
table=client.get_table(name)
rows=[dict(row) for row in client.list_rows(table)]
def encode(value):
 if isinstance(value,(datetime.datetime,datetime.date,datetime.time)):
  return value.isoformat()
 if isinstance(value,decimal.Decimal): return str(value)
 raise TypeError(type(value).__name__)
print(json.dumps({'table':table.to_api_repr(),'rows':rows},default=encode))
'''
    result = command(
        box, REDIRECT + 'python3 -c ' +
        shlex.quote('PROJECT=' + repr(PROJECT) + '\n' + program))
    return json.loads(result.stdout)


def capture(box):
    value = state(box)
    if not value['rows']:
        raise ValueError('The original BigQuery seed left no CRM customers')
    return gzip.compress(json.dumps(value).encode(), mtime=0)


def restore(box, data):
    captured = json.loads(gzip.decompress(data))
    box.files.write('/tmp/task-crm.json', json.dumps(captured), user='root')
    program = '''import json
from google.cloud import bigquery
from google.auth.credentials import AnonymousCredentials
client=bigquery.Client(project=PROJECT, credentials=AnonymousCredentials())
captured=json.load(open('/tmp/task-crm.json'))
client.create_dataset(bigquery.Dataset(PROJECT+'.woocommerce_crm'))
table=client.create_table(bigquery.Table.from_api_repr(captured['table']))
errors=client.insert_rows_json(table,captured['rows'])
if errors: raise ValueError(errors)
'''
    command(
        box, REDIRECT + 'python3 -c ' +
        shlex.quote('PROJECT=' + repr(PROJECT) + '\n' + program))
    actual = state(box)
    if (actual['table']['schema'] != captured['table']['schema']
            or actual['rows'] != captured['rows']):
        raise ValueError('Restored CRM schema or rows differ from capture')
