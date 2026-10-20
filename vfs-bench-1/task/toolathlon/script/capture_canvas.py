"""Capture a complete original Canvas task seed before any model runs."""
import argparse
import tempfile
from pathlib import Path

from e2b import Sandbox

from server.seed.business import serve
from server.seed.canvas_fixture import capture, folder
from server.seed.kubernetes import original, original_paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task',
                        choices=[
                            'canvas-new-students-notification',
                            'canvas-art-manager',
                            'canvas-homework-grader-python',
                            'canvas-arrange-exam', 'canvas-do-quiz',
                            'canvas-submit-late-work'
                        ])
    task = parser.parse_args().task
    if folder(task).exists():
        raise FileExistsError('An original Canvas capture already exists')
    with tempfile.TemporaryDirectory() as work:
        prefix = f'tasks/finalpool/{task}/initial_workspace/'
        for path in original_paths(prefix):
            target = Path(work) / path.removeprefix(prefix)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original(path))
        with serve(task, work) as record:
            source = capture(Sandbox.connect(record['sandbox_id']), task,
                             record)
            print('Captured original Canvas seed:', source['sha256'])


if __name__ == '__main__':
    main()
