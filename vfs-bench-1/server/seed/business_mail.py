"""Run the existing IMAP/SMTP fixture beside a task's store or Canvas."""
import base64
import hashlib
import imaplib
import json
import os
import re
import shlex
from pathlib import Path

import yaml

from server.seed.kubernetes import command, original, original_paths
from server.seed.seed_mail import TRANSIENT_IMAP_ERRORS, connect

REPO = Path(__file__).resolve().parents[2]


def config_path(task):
    """Use the original task's config spelling, including singular email."""
    from server.seed.business import tokens
    path = Path(tokens(task).emails_config_file)
    relative = path.relative_to(REPO / 'submodule/Toolathlon').as_posix()
    if relative not in original_paths(f'tasks/finalpool/{task}'):
        raise ValueError('Task mail configuration is not in the original tree')
    return relative


def run_args(service: dict, image: str) -> list[str]:
    """What `docker run` needs, after its own options, to start the service.

    Compose's `entrypoint` is one list; `docker run` takes its program as
    an option and the rest of it after the image.

    Args:
        service (dict): the captured compose service.
        image (str): the pinned image.

    Returns:
        list[str]: the environment, the entrypoint, the image and its
            arguments.
    """
    args = []
    for key, value in service['environment'].items():
        args += ['--env', key + '=' + value]
    program, *rest = service['entrypoint']
    return [*args, '--entrypoint', program, image, *rest]


def same_sources(captured, current):
    # A capture keeps the store it seeded and, of the mail server, only this
    # record, so the account and the image are what must match. The server's
    # start command -- `source_sha256`, the hash of `mail-sources.json` -- can
    # change while the store stays identical, and `start` compares that file
    # with compose every time it runs.
    if not captured:
        return False

    def checked(record):
        return {
            key: value
            for key, value in record.items() if key != 'source_sha256'
        }

    return checked(captured) == checked(current)


def start(box, task, stack):
    from server.seed.business import expose
    source_path = REPO / 'server/mail-sources.json'
    source = json.loads(source_path.read_text())
    current = yaml.safe_load(
        (REPO / source['source']).read_text())['services']['mail']
    if source['service'] != current:
        raise ValueError('Mail service configuration differs from capture')
    account_path = config_path(task)
    account = json.loads(original(account_path))
    if (account['imap_server'] != 'localhost'
            or account['smtp_server'] != 'localhost'
            or account['imap_port'] != 1143
            or account['smtp_port'] not in (1587, 2525)):
        raise ValueError('Task needs a different original mail transport')
    argv = [
        'sudo', 'docker', 'run', '-d', '--name', 'task-mail', '-p',
        '127.0.0.1:1143:3143', '-p', '127.0.0.1:1587:3025', '-p',
        '127.0.0.1:2525:3025'
    ]
    argv += run_args(current, source['pinned'])
    command(box, shlex.join(argv), timeout=300)
    command(
        box, 'for i in $(seq 1 60); do sudo docker exec task-mail '
        'bash -c "exec 3<>/dev/tcp/127.0.0.1/3143" 2>/dev/null '
        '&& exit 0; sleep 1; done; sudo docker logs task-mail; exit 1')
    account['imap_port'] = expose(box, 1143, 0, 8086, stack)
    account['smtp_port'] = expose(box, account['smtp_port'], 0, 8087, stack)
    local_config = REPO / f'state/business/{box.sandbox_id}-mail.json'
    local_config.parent.mkdir(parents=True, exist_ok=True)
    local_config.write_text(json.dumps(account, indent=2) + '\n')
    os.environ.update(BUSINESS_EMAIL_CONFIG=str(local_config),
                      BUSINESS_IMAP_PORT=str(account['imap_port']),
                      BUSINESS_SMTP_PORT=str(account['smtp_port']))
    connect(account).logout()
    return {
        'config_path': account_path,
        'config_sha256': hashlib.sha256(original(account_path)).hexdigest(),
        'source_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
        'image': source['pinned'],
    }


def assert_empty(task):
    account = json.loads(Path(os.environ['BUSINESS_EMAIL_CONFIG']).read_text())
    for attempt in range(3):
        client = None
        try:
            client = connect(account)
            for folder in ('INBOX', 'Sent', 'Drafts', 'Trash', 'Junk'):
                status, counts = client.select(folder, readonly=True)
                if status != 'OK' or counts != [b'0']:
                    raise ValueError('Original task did not leave an empty ' +
                                     folder)
            return
        except TRANSIENT_IMAP_ERRORS:
            if attempt == 2:
                raise
        finally:
            if client:
                try:
                    client.logout()
                except TRANSIENT_IMAP_ERRORS:
                    pass


def snapshot():
    """Keep raw messages, append order, dates and durable IMAP flags."""
    account = json.loads(Path(os.environ['BUSINESS_EMAIL_CONFIG']).read_text())
    client = connect(account)
    try:
        status, entries = client.list()
        if status != 'OK':
            raise ValueError('Cannot list original mail folders')
        folders = [shlex.split(entry.decode())[-1] for entry in entries]
        state = {}
        for name in sorted(folders):
            status, _ = client.select('"' + name + '"', readonly=True)
            if status != 'OK':
                raise ValueError('Cannot select original mail folder: ' + name)
            status, ids = client.search(None, 'ALL')
            if status != 'OK':
                raise ValueError('Cannot inventory original mail folder')
            messages = []
            for uid in ids[0].split():
                status, data = client.fetch(
                    uid, '(UID FLAGS INTERNALDATE BODY.PEEK[])')
                if status != 'OK':
                    raise ValueError('Cannot capture original message')
                header, content = next(row for row in data
                                       if isinstance(row, tuple))
                actual_uid = int(re.search(rb'UID (\d+)', header).group(1))
                # A fresh task mail server assigns IDs in append order.
                # Refuse a snapshot whose IDs cannot be faithfully restored.
                if actual_uid != len(messages) + 1:
                    raise ValueError('Original mailbox has gaps in its UIDs')
                date = re.search(rb'INTERNALDATE ("[^"]+")',
                                 header).group(1).decode()
                flags = sorted(flag.decode()
                               for flag in imaplib.ParseFlags(header)
                               if flag != b'\\Recent')
                messages.append({
                    'uid': actual_uid,
                    'date': date,
                    'flags': flags,
                    'base64': base64.b64encode(content).decode()
                })
            state[name] = messages
        return state
    finally:
        client.logout()


def restore(state):
    account = json.loads(Path(os.environ['BUSINESS_EMAIL_CONFIG']).read_text())
    client = connect(account)
    try:
        for name, messages in state.items():
            client.create('"' + name + '"')
            status, count = client.select('"' + name + '"')
            if status != 'OK' or count != [b'0']:
                raise ValueError('Mail restore requires an empty folder')
            for message in messages:
                status, _ = client.append(
                    '"' + name + '"', '(' + ' '.join(message['flags']) + ')',
                    message['date'], base64.b64decode(message['base64']))
                if status != 'OK':
                    raise ValueError('Could not restore original message')
    finally:
        client.logout()
    if snapshot() != state:
        raise ValueError('Restored message bytes, dates, flags or UIDs differ')
