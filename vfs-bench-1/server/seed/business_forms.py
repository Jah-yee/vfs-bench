"""Reuse Mirage's Forms/Drive API for the original commerce workflows."""
import json
import os
import select
import subprocess
from pathlib import Path

from server.clients import gws
from server.seed.business_sheets import MIRAGE_SOURCE, start_runtime

REPO = Path(__file__).resolve().parents[2]
TASKS = {'woocommerce-customer-survey', 'woocommerce-product-recall'}


def start(box, task, stack):
    record = start_runtime(box, stack, 'server/fakes/forms_api.mjs',
                           'redirect/forms/sitecustomize.py')
    gws.reset()
    return record


def start_cli(stack):
    from server.mcp.setup_papers_forms import source_root
    source_root('forms-mcp')
    params = {
        'command': 'node',
        'args': [str(REPO / 'server/clients/forms.mjs')],
        'env': {
            **os.environ,
            'GWS_MOCK_URL': os.environ['GWS_URL'],
            'GOOGLE_CLIENT_ID': 'fixture',
            'GOOGLE_CLIENT_SECRET': 'fixture',
            'GOOGLE_REFRESH_TOKEN': gws.TOKEN,
        }
    }
    # This worker only sees fixture credentials, not model or E2B secrets.
    params['env'] = {
        key: params['env'][key]
        for key in ('PATH', 'GWS_MOCK_URL', 'GOOGLE_CLIENT_ID',
                    'GOOGLE_CLIENT_SECRET', 'GOOGLE_REFRESH_TOKEN')
    }
    process = subprocess.Popen([params['command'], *params['args']],
                               env=params['env'],
                               stdout=subprocess.PIPE,
                               text=True)

    from server.seed.papers import close
    stack.callback(close, process)
    if not select.select([process.stdout], [], [], 30)[0]:
        raise TimeoutError('Original Forms handler worker did not start')
    line = process.stdout.readline()
    if not line:
        raise RuntimeError('Original Forms handler worker failed to start')
    os.environ['FORMS_CLI_URL'] = 'http://127.0.0.1:' + str(
        json.loads(line)['port'])


def validate_seed():
    forms = gws.call(
        'GET', '/drive/v3/files?q=' +
        gws.quote("mimeType='application/vnd.google-apps.form'"))['files']
    if forms:
        raise ValueError(
            'Original Forms preprocessor did not leave an empty collection')


def same_sources(captured, current):
    """The npm closure and this repo's adapters must match the capture.

    Mirage's own source under `integ/` is recorded but not compared, for
    the reason `MIRAGE_SOURCE` gives. `validate_seed` verifies the original
    empty form collection after every restore either way.
    """
    if not captured:
        return False

    def checked(record):
        return {
            name: sha
            for name, sha in record['inputs_sha256'].items()
            if not name.startswith(MIRAGE_SOURCE)
        }

    return checked(captured) == checked(current)
