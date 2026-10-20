"""Freeze image digests and WP-CLI bytes selected by original service setup."""
import hashlib
import json
import re
from pathlib import Path

import requests

from server.seed.kubernetes import original

REPO = Path(__file__).resolve().parents[3]
DEST = REPO / 'server/business-sources.json'


def get(url, **kwargs):
    response = requests.get(url, timeout=90, **kwargs)
    response.raise_for_status()
    return response


def main():
    result = {'images': {}, 'setup_sha256': {}}
    for service, images in {
            'canvas': ['lbjay/canvas-docker'],
            'woocommerce': ['mysql:8.0', 'wordpress:6.8.2-php8.2-apache'],
    }.items():
        source = original(f'deployment/{service}/scripts/setup.sh')
        result['setup_sha256'][service] = hashlib.sha256(source).hexdigest()
        result['images'][service] = []
        for name in images:
            if name.encode() not in source:
                raise ValueError('Image no longer selected by original setup')
            repository, _, tag = name.partition(':')
            if '/' not in repository:
                repository = 'library/' + repository
            token = get('https://auth.docker.io/token',
                        params={
                            'service': 'registry.docker.io',
                            'scope': f'repository:{repository}:pull'
                        }).json()['token']
            manifest = get(
                f'https://registry-1.docker.io/v2/{repository}/'
                f'manifests/{tag or "latest"}',
                headers={
                    'Authorization':
                    'Bearer ' + token,
                    'Accept':
                    'application/vnd.oci.image.index.v1+json,'
                    'application/vnd.docker.distribution.'
                    'manifest.list.v2+json,'
                    'application/vnd.docker.distribution.manifest.v2+json'
                })
            digest = 'sha256:' + hashlib.sha256(manifest.content).hexdigest()
            if digest != manifest.headers['Docker-Content-Digest']:
                raise ValueError('Registry manifest checksum mismatch')
            result['images'][service].append({
                'source':
                name,
                'pinned':
                repository + '@' + digest
            })
    setup = original('deployment/woocommerce/scripts/setup.sh').decode()
    url = re.search(
        r'https://raw.githubusercontent.com/wp-cli/builds/gh-pages/[^\s]+',
        setup).group(0)
    commit = get('https://api.github.com/repos/wp-cli/builds/commits',
                 params={
                     'path': 'phar/wp-cli.phar',
                     'per_page': 1
                 }).json()[0]['sha']
    pinned = url.replace('/gh-pages/', '/' + commit + '/')
    data = get(pinned).content
    result['wp_cli'] = {
        'source': url,
        'url': pinned,
        'sha256': hashlib.sha256(data).hexdigest()
    }
    result['woocommerce_version'] = re.search(
        r'plugin install woocommerce --version=([^\s]+)', setup).group(1)
    DEST.write_text(json.dumps(result, indent=2) + '\n')
    print('Captured original service image digests and WP-CLI revision')


if __name__ == '__main__':
    main()
