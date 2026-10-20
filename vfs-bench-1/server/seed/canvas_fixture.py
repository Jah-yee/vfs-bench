"""Snapshot the original Canvas database and validate its visible state."""
import gzip
import hashlib
import json
import shlex
from pathlib import Path

import requests

from server.seed.kubernetes import command

REPO = Path(__file__).resolve().parents[2]


def folder(task):
    return REPO / 'task/toolathlon' / task / 'shared/fixtures/canvas'


def api_state(task):
    from server.seed.business import tokens
    session = requests.Session()
    session.headers['Authorization'] = 'Bearer ' + tokens(
        task).canvas_api_token
    base = 'http://localhost:10001/api/v1/'

    def listing(path):
        rows = []
        page = 1
        while True:
            response = session.get(base + path,
                                   params={
                                       'page': page,
                                       'per_page': 100
                                   },
                                   timeout=60)
            response.raise_for_status()
            batch = response.json()
            if not isinstance(batch, list):
                raise ValueError('Expected a Canvas collection: ' + path)
            rows.extend(batch)
            if 'next' not in response.links:
                return rows
            page += 1

    try:
        state = {
            'courses': listing('courses'),
            'conversations': listing('conversations')
        }
        course_paths = ['courses']
        if task in ('canvas-new-students-notification', 'canvas-art-manager'):
            for kind in ('courses', 'users'):
                path = 'accounts/1/' + kind
                state[path] = listing(path)
            course_paths.append('accounts/1/courses')
        # The original preprocessors create their courses in account 1.
        # The admin's own enrollment list can be empty even when they exist.
        courses = {
            row['id']: row
            for path in course_paths
            for row in state[path]
        }
        for course in courses.values():
            prefix = f"courses/{course['id']}"
            for kind in ('users', 'enrollments', 'assignments', 'quizzes'):
                state[prefix + '/' + kind] = listing(prefix + '/' + kind)
            if task in ('canvas-arrange-exam', 'canvas-do-quiz',
                        'canvas-submit-late-work', 'canvas-art-manager'):
                state[prefix +
                      '/discussion_topics?only_announcements=true'] = listing(
                          prefix +
                          '/discussion_topics?only_announcements=true')
            if task == 'canvas-do-quiz':
                for quiz in state[prefix + '/quizzes']:
                    path = prefix + f"/quizzes/{quiz['id']}/submissions"
                    response = session.get(base + path, timeout=60)
                    response.raise_for_status()
                    state[path] = response.json()
            for assignment in state[prefix + '/assignments']:
                path = prefix + f"/assignments/{assignment['id']}/submissions"
                if task in ('canvas-arrange-exam', 'canvas-do-quiz',
                            'canvas-submit-late-work'):
                    response = session.get(base + path + '/self', timeout=60)
                    response.raise_for_status()
                    state[path + '/self'] = response.json()
                else:
                    state[path] = listing(path)
        return state
    finally:
        session.close()


def state_hashes(state, task=None):
    # Reading a course updates the student's activity timestamp. Compare
    # persisted task content without this read-induced activity metadata.
    if task in ('canvas-homework-grader-python', 'canvas-arrange-exam',
                'canvas-do-quiz', 'canvas-submit-late-work'):
        state = {
            path: ([{
                key: value
                for key, value in row.items() if key != 'last_activity_at'
            } for row in rows] if path.endswith('/enrollments') else rows)
            for path, rows in state.items()
        }
    # Canvas calculates these from the current clock for unsubmitted late
    # work: `seconds_late` grows, and `missing` flips once the due date has
    # passed, which canvas-do-quiz's did after its capture. Ignore them only
    # in snapshot comparisons; both arms still receive the native API
    # response, and the capture keeps the raw values. One submission or a
    # course's list of them, since the tasks read both.
    if task in ('canvas-submit-late-work', 'canvas-do-quiz',
                'canvas-new-students-notification'):

        def settled(row):
            if not isinstance(
                    row, dict) or row.get('workflow_state') != 'unsubmitted':
                return row
            return {
                key: value
                for key, value in row.items()
                if key not in ('seconds_late', 'missing')
            }

        state = {
            path:
            (settled(rows) if path.endswith('/submissions/self') else
             [settled(row)
              for row in rows] if path.endswith('/submissions') else rows)
            for path, rows in state.items()
        }
    return {
        path:
        hashlib.sha256(
            json.dumps(rows, sort_keys=True,
                       separators=(',', ':')).encode()).hexdigest()
        for path, rows in state.items()
    }


def database(box, operation):
    if operation not in ('capture', 'restore'):
        raise ValueError('Unknown database operation')
    # Use Canvas's actual connection settings, without printing credentials.
    program = '''config = ActiveRecord::Base.connection_config
env = {"PGPASSWORD" => config[:password].to_s}
args = []
args += ["--host", config[:host]] if config[:host]
args += ["--port", config[:port].to_s] if config[:port]
args += ["--username", config[:username]] if config[:username]
args += ["--dbname", config[:database]]
'''
    if operation == 'capture':
        program += ('ok = system(env, "pg_dump", *args, "--format=custom", '
                    '"--no-owner", "--no-acl", "--file=/tmp/canvas.dump")\n')
    else:
        # Restore into an empty schema so cleanup never depends on which
        # dated partitions exist in the fresh image. Its pg_restore skips
        # creating public outside --clean mode, so recreate it here.
        program += ('ActiveRecord::Base.connection.execute('
                    '"DROP SCHEMA public CASCADE; CREATE SCHEMA public")\n'
                    'ok = system(env, "pg_restore", *args, '
                    '"--exit-on-error", "--no-owner", "--no-acl", '
                    '"/tmp/canvas.dump")\n')
    program += 'abort "Canvas database operation failed" unless ok\n'
    box.files.write('/tmp/canvas-database.rb', program, user='root')
    command(
        box, 'sudo docker cp /tmp/canvas-database.rb '
        'canvas-docker:/tmp/canvas-database.rb')
    command(
        box,
        'sudo docker exec canvas-docker bash -c ' +
        shlex.quote('cd /opt/canvas/canvas-lms && GEM_HOME=/opt/canvas/.gems '
                    '/opt/canvas/.gems/bin/bundle exec rails runner '
                    '/tmp/canvas-database.rb'),
        timeout=180)


def capture(box, task, record):
    destination = folder(task)
    if destination.exists():
        raise FileExistsError('Refusing to replace an existing Canvas capture')
    state = api_state(task)
    hashes = state_hashes(state, task)
    database(box, 'capture')
    command(
        box,
        'sudo docker cp canvas-docker:/tmp/canvas.dump /tmp/canvas.dump && '
        'sudo chmod 644 /tmp/canvas.dump')
    data = {
        'api.json.gz':
        gzip.compress(json.dumps(state).encode(), mtime=0),
        'database.dump':
        box.files.read('/tmp/canvas.dump', format='bytes'),
        'workspace.tar.gz':
        box.files.read('/tmp/workspace.tar.gz', format='bytes'),
    }
    if task in ('canvas-arrange-exam', 'canvas-do-quiz',
                'canvas-submit-late-work'):
        command(
            box, 'sudo tar -czf /tmp/private.tar.gz -C ' +
            shlex.quote('/opt/toolathlon/tasks/finalpool/' + task) + ' files')
        data['private.tar.gz'] = box.files.read('/tmp/private.tar.gz',
                                                format='bytes')
    if task == 'canvas-submit-late-work':
        command(
            box, 'sudo docker exec canvas-docker sh -c ' + shlex.quote(
                'cd /opt/canvas/canvas-lms && '
                'if test -d tmp/files; then '
                'tar -czf /tmp/media.tar.gz tmp/files; '
                'else tar -czf /tmp/media.tar.gz --files-from /dev/null; fi') +
            ' && sudo docker cp canvas-docker:/tmp/media.tar.gz '
            '/tmp/media.tar.gz && '
            'sudo chmod 644 /tmp/media.tar.gz')
        data['media.tar.gz'] = box.files.read('/tmp/media.tar.gz',
                                              format='bytes')
        data['file_store.yml'] = command(
            box, 'sudo docker exec canvas-docker '
            'cat /opt/canvas/canvas-lms/config/file_store.yml').stdout.encode(
            )
    if record.get('mail'):
        from server.seed import business_mail
        data['mail.json.gz'] = gzip.compress(json.dumps(
            business_mail.snapshot()).encode(),
                                             mtime=0)
    after = api_state(task)
    if state_hashes(after, task) != hashes:
        (REPO /
         f'state/business/{box.sandbox_id}-capture.json.gz').write_bytes(
             gzip.compress(json.dumps({
                 'before': state,
                 'after': after
             }).encode(),
                           mtime=0))
        raise ValueError('Canvas changed while its fixture was captured')
    destination.mkdir(parents=True)
    for name, content in data.items():
        (destination / name).write_bytes(content)
    source = {
        'task': task,
        'service': record,
        'api_sha256': hashes,
        'sha256': {
            name: hashlib.sha256(content).hexdigest()
            for name, content in data.items()
        }
    }
    (destination /
     'source.json').write_text(json.dumps(source, indent=2) + '\n')
    return source


def restore(box, task, inputs, remote_mcp):
    base = folder(task)
    source = json.loads((base / 'source.json').read_text())
    if source['task'] != task or source['service']['inputs_sha256'] != inputs:
        raise ValueError('Original Canvas sources differ from the capture')
    if source['service']['mcp'] != remote_mcp:
        raise ValueError(
            'Remote MCP dependencies differ from the Canvas capture')
    dependencies = json.loads(
        (REPO / 'server/business-sources.json').read_text())
    if source['service']['dependency_sources'] != dependencies:
        raise ValueError('Canvas service dependencies differ from capture')
    for name, expected in source['sha256'].items():
        data = (base / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Canvas fixture checksum mismatch: ' + name)
        if name not in ('api.json.gz', 'mail.json.gz'):
            box.files.write('/tmp/' + name, data, user='root')
    command(
        box, 'sudo docker exec canvas-docker supervisorctl stop '
        'canvas_web canvas_worker')
    command(
        box,
        'sudo docker cp /tmp/database.dump canvas-docker:/tmp/canvas.dump')
    database(box, 'restore')
    if 'media.tar.gz' in source['sha256']:
        actual = command(
            box, 'sudo docker exec canvas-docker cat '
            '/opt/canvas/canvas-lms/config/file_store.yml').stdout.encode()
        if actual != (base / 'file_store.yml').read_bytes():
            raise ValueError('Canvas file storage configuration changed')
        command(
            box, 'sudo docker cp /tmp/media.tar.gz '
            'canvas-docker:/tmp/media.tar.gz && '
            'sudo docker exec canvas-docker sh -c ' +
            shlex.quote('cd /opt/canvas/canvas-lms && rm -rf tmp/files && '
                        'tar -xzf /tmp/media.tar.gz && '
                        'if test -d tmp/files; then '
                        'chown -R canvas:canvas tmp/files; fi'))
    command(
        box, 'sudo docker exec canvas-docker supervisorctl start '
        'canvas_web canvas_worker')
    command(
        box, 'for i in $(seq 1 90); do curl -fsS http://localhost:10001/login '
        '>/dev/null && exit 0; sleep 1; done; exit 1')
    command(
        box, 'sudo find /work -mindepth 1 -delete && '
        'sudo tar -xzf /tmp/workspace.tar.gz -C /work && '
        'sudo chown -R user:user /work')
    if 'private.tar.gz' in source['sha256']:
        command(
            box, 'sudo tar -xzf /tmp/private.tar.gz -C ' +
            shlex.quote('/opt/toolathlon/tasks/finalpool/' + task))
    if 'mail.json.gz' in source['sha256']:
        from server.seed import business_mail
        business_mail.restore(
            json.loads(gzip.decompress((base / 'mail.json.gz').read_bytes())))
    return source
