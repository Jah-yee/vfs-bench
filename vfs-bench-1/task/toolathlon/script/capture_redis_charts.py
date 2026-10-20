import gzip
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

REPO = Path(__file__).resolve().parents[3]
DEST = REPO / 'task/toolathlon/k8s-redis-helm-upgrade/shared/fixtures/charts'
ROOT = REPO / 'submodule/Toolathlon'
CHART = 'redis'
OCI = 'oci://registry-1.docker.io/'
LAYER = 'application/vnd.cncf.helm.chart.content.v1.tar+gzip'
MANIFEST = 'application/vnd.oci.image.manifest.v1+json'
HEADERS = {'User-Agent': 'Helm/3.14.0'}


def original(name):
    return subprocess.check_output([
        'git', '-C',
        str(ROOT), 'show',
        f'HEAD:tasks/finalpool/k8s-redis-helm-upgrade/{name}'
    ]).decode()


def versions():
    script = original('scripts/init_redis_helm.sh')
    prompt = original('docs/task.md')
    base = re.search(r'helm_repo_url="([^"]+)"', script).group(1)
    initial = re.search(r'initial_version="([^"]+)"', script).group(1)
    target = re.search(r'version (\d+\.\d+\.\d+)', prompt).group(1)
    return base, initial, target


def digest(entry):
    # The index spells the oldest entries' digests `sha256:<hex>` and the
    # rest bare, which is Bitnami's inconsistency and not two hashes.
    return entry['digest'].removeprefix('sha256:')


def layer_digest(manifest):
    """The chart layer an OCI manifest names, as the index spells it."""
    layer = next(layer for layer in json.loads(manifest)['layers']
                 if layer['mediaType'] == LAYER)
    return layer['digest'].removeprefix('sha256:')


def fetch_archive(session, entry):
    """One chart's original bytes, checked against the index's own digest."""
    url = entry['urls'][0]
    manifest = None
    if url.startswith(OCI):
        repository, version = url[len(OCI):].rsplit(':', 1)
        # One token per chart: a pull token outlives a few fetches, not the
        # hundred-odd this capture makes in a row.
        token = session.get('https://auth.docker.io/token',
                            params={
                                'service': 'registry.docker.io',
                                'scope': f'repository:{repository}:pull'
                            },
                            timeout=90)
        token.raise_for_status()
        headers = {
            'Authorization': 'Bearer ' + token.json()['token'],
            'Accept': MANIFEST
        }
        reply = session.get(
            f'https://registry-1.docker.io/v2/{repository}/'
            f'manifests/{version}',
            headers=headers,
            timeout=90)
        reply.raise_for_status()
        manifest = reply.content
        if layer_digest(manifest) != digest(entry):
            raise ValueError(
                'OCI chart layer does not match the original index')
        response = session.get(
            f"https://registry-1.docker.io/v2/{repository}/"
            f"blobs/sha256:{digest(entry)}",
            headers=headers,
            timeout=90)
    else:
        response = session.get(url, headers=HEADERS, timeout=90)
    response.raise_for_status()
    data = response.content
    if hashlib.sha256(data).hexdigest() != digest(entry):
        raise ValueError(f"Redis chart {entry['version']} does not match "
                         'the original artifact')
    return data, manifest


def cached(entry, path, manifest):
    """Whether the archive on disk, and for an OCI chart its manifest, hold.

    Both are what the receipt hashes, so a capture that stopped between
    the two writes, or left a manifest naming other bytes, fetches the
    chart again rather than reporting it complete.
    """
    if not (path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()
            == digest(entry)):
        return False
    if not entry['urls'][0].startswith(OCI):
        return True
    try:
        return manifest.is_file() and layer_digest(
            manifest.read_bytes()) == digest(entry)
    except (ValueError, KeyError, StopIteration):
        return False


def archives(session, parsed):
    """Every Redis archive the index advertises, in the index's own order.

    A file already on disk whose bytes hash to the index's digest, with the
    manifest that names it where the chart is an OCI one, is kept rather
    than fetched again, so a capture interrupted by the network resumes
    where it stopped and a re-run against an unchanged index moves no
    bytes.
    """
    records = []
    for entry in parsed['entries'][CHART]:
        path = DEST / f"{CHART}-{entry['version']}.tgz"
        manifest = path.with_name(f"{CHART}-{entry['version']}.manifest.json")
        if not cached(entry, path, manifest):
            data, manifest_data = fetch_archive(session, entry)
            path.write_bytes(data)
            if manifest_data is not None:
                manifest.write_bytes(manifest_data)
            print('Captured', path.name, flush=True)
        record = {
            'url': entry['urls'][0],
            'path': path.name,
            'sha256': digest(entry)
        }
        if entry['urls'][0].startswith(OCI):
            record['manifest_sha256'] = hashlib.sha256(
                manifest.read_bytes()).hexdigest()
        records.append(record)
    return records


def write_source(source, records):
    source['files'] = records
    source['archives_captured_at'] = datetime.now(timezone.utc).isoformat()
    (DEST / 'source.json').write_text(json.dumps(source, indent=2) + '\n')


def main():
    base, initial, target = versions()
    with requests.Session() as session:
        response = session.get(base + '/index.yaml',
                               headers=HEADERS,
                               timeout=90)
        response.raise_for_status()
        index = response.content
        parsed = yaml.load(index, Loader=yaml.CSafeLoader)
        # Preserve the actual latest version: a bare upgrade must not
        # silently become the task's requested version just because our
        # cache is smaller.
        latest = parsed['entries'][CHART][0]['version']
        DEST.mkdir(parents=True, exist_ok=True)
        (DEST / 'index.yaml.gz').write_bytes(gzip.compress(index, mtime=0))
        records = [{
            'url': base + '/index.yaml',
            'path': 'index.yaml.gz',
            'sha256': hashlib.sha256(index).hexdigest(),
            'encoding': 'gzip'
        }]
        records += archives(session, parsed)
    write_source(
        {
            'captured_at':
            datetime.now(timezone.utc).isoformat(),
            'initial':
            initial,
            'target':
            target,
            'latest':
            latest,
            'upstream_revision':
            subprocess.check_output(
                ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                text=True).strip(),
        }, records)
    print('Captured original index and', len(records) - 1, 'Redis charts')


def complete():
    """Fetch what the frozen index advertises without refetching the index.

    The index is the capture: what an agent lists and which version a bare
    upgrade picks both come from it, so completing the archives behind it
    must not move it to whatever Bitnami publishes today.
    """
    source = json.loads((DEST / 'source.json').read_text())
    index = gzip.decompress((DEST / 'index.yaml.gz').read_bytes())
    if hashlib.sha256(index).hexdigest() != source['files'][0]['sha256']:
        raise ValueError('Helm index capture checksum mismatch')
    parsed = yaml.load(index, Loader=yaml.CSafeLoader)
    with requests.Session() as session:
        records = [source['files'][0], *archives(session, parsed)]
    write_source(source, records)
    print('Completed',
          len(records) - 1, 'Redis charts behind the frozen index')


if __name__ == '__main__':
    {
        'capture': main,
        'complete': complete
    }[sys.argv[1] if len(sys.argv) > 1 else 'capture']()
