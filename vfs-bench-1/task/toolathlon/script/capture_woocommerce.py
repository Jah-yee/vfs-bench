"""Capture an original WooCommerce seed; both measured arms restore it."""
import argparse
import tempfile
from pathlib import Path

from e2b import Sandbox

from server.seed.business import serve
from server.seed.kubernetes import original, original_paths
from server.seed.woocommerce_fixture import PRIVATE_FILES, capture, folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task', choices=PRIVATE_FILES)
    task = parser.parse_args().task
    if folder(task).exists():
        raise FileExistsError('An original WooCommerce capture already exists')
    with tempfile.TemporaryDirectory() as work:
        prefix = f'tasks/finalpool/{task}/initial_workspace/'
        for path in original_paths(prefix):
            target = Path(work) / path.removeprefix(prefix)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original(path))
        with serve(task, work) as record:
            result = capture(Sandbox.connect(record['sandbox_id']), task,
                             record)
            print('Captured original WooCommerce seed:', result['sha256'])


if __name__ == '__main__':
    main()
