"""Fresh local mailboxes for the original research-task sender/receivers."""
import hashlib
import imaplib
import json
import os
import subprocess
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

from server.seed.business_mail import config_path, run_args
from server.seed.kubernetes import original
from server.seed.seed_mail import connect

REPO = Path(__file__).resolve().parents[2]


@contextmanager
def serve(task, directory):
    record = json.loads((REPO / 'server/mail-sources.json').read_text())
    args = [
        'docker', 'run', '--detach', '--rm', '--publish', '127.0.0.1::3143',
        '--publish', '127.0.0.1::3025'
    ]
    args += run_args(record['service'], record['pinned'])
    container = subprocess.check_output(args, text=True).strip()
    with ExitStack() as stack:
        stack.callback(subprocess.run, ['docker', 'rm', '-f', container],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

        def port(number):
            return int(
                subprocess.check_output(
                    ['docker', 'port', container,
                     str(number) + '/tcp'],
                    text=True).strip().rsplit(':', 1)[1])

        imap_port, smtp_port = port(3143), port(3025)
        path = config_path(task)
        account = json.loads(original(path))
        account.update(imap_server='127.0.0.1',
                       smtp_server='127.0.0.1',
                       imap_port=imap_port,
                       smtp_port=smtp_port)
        target = directory / 'mail.json'
        target.write_text(json.dumps(account))
        os.environ.update(BUSINESS_EMAIL_CONFIG=str(target),
                          BUSINESS_IMAP_PORT=str(imap_port),
                          BUSINESS_SMTP_PORT=str(smtp_port))
        for attempt in range(120):
            try:
                connect(account).logout()
                break
            except (OSError, imaplib.IMAP4.abort, imaplib.IMAP4.error):
                # `IMAP4.error` too: the container answers before it has
                # provisioned the account, and that read as "LOGIN failed"
                # rather than as a refused connection.
                if attempt == 119:
                    raise
                time.sleep(.25)
        # Original preprocessing clears mail; a new service starts empty.
        yield {
            'config_source': path,
            'config_sha256': hashlib.sha256(original(path)).hexdigest(),
            'image': record['pinned'],
            'initial_messages': 0
        }
