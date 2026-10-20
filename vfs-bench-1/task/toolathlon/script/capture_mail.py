"""Pin the existing mail fixture image for the E2B service harness."""
import hashlib
import json
from pathlib import Path

import yaml

from task.toolathlon.script.capture_business_sources import get

REPO = Path(__file__).resolve().parents[3]


def main():
    config = yaml.safe_load(
        (REPO / 'docker/compose.yml').read_text())['services']['mail']
    repository, tag = config['image'].rsplit(':', 1)
    token = get('https://auth.docker.io/token',
                params={
                    'service': 'registry.docker.io',
                    'scope': f'repository:{repository}:pull',
                }).json()['token']
    manifest = get(
        f'https://registry-1.docker.io/v2/{repository}/manifests/{tag}',
        headers={
            'Authorization':
            'Bearer ' + token,
            'Accept':
            'application/vnd.oci.image.index.v1+json,'
            'application/vnd.docker.distribution.manifest.list.v2+json,'
            'application/vnd.docker.distribution.manifest.v2+json',
        })
    digest = 'sha256:' + hashlib.sha256(manifest.content).hexdigest()
    if digest != manifest.headers['Docker-Content-Digest']:
        raise ValueError('Mail image manifest checksum mismatch')
    record = {
        'source': 'docker/compose.yml',
        'service': config,
        'pinned': repository + '@' + digest,
    }
    (REPO / 'server/mail-sources.json'
     ).write_text(json.dumps(record, indent=2) + '\n')
    print('Captured mail image:', record['pinned'])


if __name__ == '__main__':
    main()
