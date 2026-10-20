"""Pinned native Helm and an isolated repository of original chart archives."""
import functools
import gzip
import hashlib
import http.server
import io
import json
import os
import platform
import shutil
import tarfile
import tempfile
import threading
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
FIXTURE = (REPO / 'task/toolathlon/k8s-redis-helm-upgrade' /
           'shared/fixtures/charts')


def asset(system):
    return json.loads(
        (REPO / 'server/kubernetes-binaries.json').read_text())['helm-' +
                                                                system]


def download(system):
    entry = asset(system)
    data = urllib.request.urlopen(entry['url'], timeout=60).read()
    if hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError('Helm release checksum mismatch')
    return data


def main():
    system = platform.system().lower() + '-' + {
        'arm64': 'arm64',
        'aarch64': 'arm64',
        'x86_64': 'amd64'
    }[platform.machine()]
    data = download(system)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        binary = archive.extractfile(system + '/helm').read()
    target = REPO / 'vendor/kubernetes-bin/helm'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(binary)
    target.chmod(0o755)
    target.with_name('helm-source.json').write_text(
        json.dumps(
            {
                **asset(system), 'binary_sha256':
                hashlib.sha256(binary).hexdigest()
            },
            indent=2) + '\n')


def install_remote(box):
    data = download('linux-amd64')
    box.files.write('/tmp/helm.tar.gz', data, user='root')
    result = box.commands.run(
        'sudo tar -xzf /tmp/helm.tar.gz -C /tmp && '
        'sudo install /tmp/linux-amd64/helm /usr/local/bin/helm-native',
        timeout=60)
    if result.exit_code:
        raise RuntimeError(result.stderr)

    with tempfile.TemporaryDirectory() as directory:
        repository = Path(directory) / 'charts'
        prepare_repository(repository)
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as archive:
            archive.add(repository, arcname='charts')
        box.files.write('/tmp/redis-charts.tar.gz',
                        data.getvalue(),
                        user='root')
    box.commands.run('sudo tar -xzf /tmp/redis-charts.tar.gz -C /opt',
                     timeout=30)
    box.commands.run(
        'python3 -m http.server 8085 --bind 127.0.0.1 --directory /opt/charts',
        background=True,
        timeout=0)
    wrapper = (REPO / 'server/helm.sh').read_text().replace(
        '#!/bin/bash',
        '#!/bin/bash\nexport HELM_NATIVE=/usr/local/bin/helm-native\n'
        'export HELM_FIXTURE_URL=http://127.0.0.1:8085')
    box.files.write('/usr/local/bin/helm', wrapper, user='root')
    box.commands.run('sudo chmod 755 /usr/local/bin/helm', timeout=30)


def prepare_repository(repository):
    """Rewrite artifact transport only, keeping all original index entries."""
    source = json.loads((FIXTURE / 'source.json').read_text())
    index = gzip.decompress((FIXTURE / 'index.yaml.gz').read_bytes())
    if hashlib.sha256(index).hexdigest() != source['files'][0]['sha256']:
        raise ValueError('Helm index capture checksum mismatch')
    parsed = yaml.load(index, Loader=yaml.CSafeLoader)
    repository.mkdir(parents=True)
    for record in source['files'][1:]:
        path = FIXTURE / record['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Redis chart capture checksum mismatch')
        shutil.copyfile(path, repository / path.name)
        entry = next(entry for entry in parsed['entries']['redis']
                     if record['url'] in entry['urls'])
        entry['urls'] = [path.name]
    (repository / 'index.yaml').write_text(
        yaml.dump(parsed, Dumper=yaml.CSafeDumper))


def configure(folder: Path, workdir: str, stack):
    binary = REPO / 'vendor/kubernetes-bin/helm'
    record = json.loads(binary.with_name('helm-source.json').read_text())
    assets = json.loads((REPO / 'server/kubernetes-binaries.json').read_text())
    release = {
        key: value
        for key, value in record.items() if key != 'binary_sha256'
    }
    if (release not in assets.values() or hashlib.sha256(
            binary.read_bytes()).hexdigest() != record['binary_sha256']):
        raise ValueError('Local Helm differs from its pinned release')
    repository = folder / 'charts'
    prepare_repository(repository)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(repository))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    stack.callback(server.server_close)
    stack.callback(server.shutdown)
    url = f'http://127.0.0.1:{server.server_port}'
    config = folder / 'helm-config'
    config.mkdir()
    (config / 'repositories.yaml').write_text(
        yaml.safe_dump({
            'apiVersion': 'v1',
            'repositories': [{
                'name': 'bitnami',
                'url': url
            }]
        }))
    cache = folder / 'helm-cache/repository'
    cache.mkdir(parents=True)
    shutil.copyfile(repository / 'index.yaml', cache / 'bitnami-index.yaml')
    wrapper = folder / 'helm'
    shutil.copyfile(REPO / 'server/helm.sh', wrapper)
    wrapper.chmod(0o755)
    os.environ.update(HELM=str(wrapper),
                      HELM_NATIVE=str(binary),
                      HELM_FIXTURE_URL=url,
                      HELM_CONFIG_HOME=str(config),
                      HELM_CACHE_HOME=str(folder / 'helm-cache'),
                      HELM_DATA_HOME=str(folder / 'helm-data'))


if __name__ == '__main__':
    main()
