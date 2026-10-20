"""Keep cluster authentication in a harness-owned local proxy."""
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import yaml


@contextmanager
def serve(config: dict, binary: Path):
    """Yield a credential-free kubeconfig; remove private state on exit."""
    context = next(row for row in config['contexts']
                   if row['name'] == config['current-context'])
    with tempfile.TemporaryDirectory(prefix='kubernetes-auth-') as scratch:
        private = Path(scratch) / 'config.yaml'
        private.write_text(yaml.safe_dump(config))
        private.chmod(0o600)
        with tempfile.TemporaryFile(mode='w+b') as output:
            process = subprocess.Popen(
                [
                    str(binary), '--kubeconfig=' + str(private), 'proxy',
                    '--address=127.0.0.1', '--port=0', '--reject-paths=^$'
                ],
                # Embedded credentials need no external env or auth plugins.
                env={},
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=output)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    match = re.search(
                        rb'Starting to serve on 127\.0\.0\.1:(\d+)',
                        os.pread(output.fileno(), 65536, 0))
                    if match:
                        break
                    if process.poll() is not None:
                        raise RuntimeError(
                            'Kubernetes authentication proxy exited')
                    time.sleep(.05)
                else:
                    raise TimeoutError(
                        'Kubernetes authentication proxy did not start')
                # Construct connection identity without copying credentials.
                identity = context['context']
                yield {
                    'apiVersion':
                    'v1',
                    'kind':
                    'Config',
                    'preferences': {},
                    'current-context':
                    context['name'],
                    'contexts': [{
                        'name': context['name'],
                        'context': {
                            key: identity[key]
                            for key in ('cluster', 'user', 'namespace')
                            if key in identity
                        },
                    }],
                    'clusters': [{
                        'name': identity['cluster'],
                        'cluster': {
                            'server': 'http://127.0.0.1:' + match[1].decode(),
                            # client-node requires this for plain HTTP. It
                            # applies only to the loopback proxy; the private
                            # upstream connection still verifies cluster TLS.
                            'insecure-skip-tls-verify': True,
                        },
                    }],
                    'users': [{
                        'name': identity['user'],
                        'user': {}
                    }],
                }
            finally:
                from server.seed.papers import close
                close(process, timeout=5)
