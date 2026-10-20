import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'task/toolathlon/script'))
import capture_redis_charts as capture  # noqa: E402


def manifest_naming(digest):
    return json.dumps({
        'layers': [{
            'mediaType': capture.LAYER,
            'digest': 'sha256:' + digest
        }]
    }).encode()


class RedisChartsCapture(unittest.TestCase):

    def test_a_cache_hit_needs_the_oci_manifest_too(self):
        data = b'chart bytes'
        sha = hashlib.sha256(data).hexdigest()
        manifest = manifest_naming(sha)
        entries = [{
            'version': '1.0.0',
            'digest': sha,
            'urls': [capture.OCI + 'bitnamicharts/redis:1.0.0']
        }, {
            'version': '0.9.0',
            'digest': 'sha256:' + sha,
            'urls': ['https://charts.example/redis-0.9.0.tgz']
        }]
        index = {'entries': {'redis': entries}}
        fetched = []

        def fetch(session, entry):
            fetched.append(entry['version'])
            oci = entry['urls'][0].startswith(capture.OCI)
            return data, manifest if oci else None

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(capture, 'DEST', Path(folder)), \
                patch.object(capture, 'fetch_archive', fetch):
            archive = Path(folder) / 'redis-1.0.0.tgz'
            # Both archives are on disk; the OCI one lost its manifest.
            archive.write_bytes(data)
            (Path(folder) / 'redis-0.9.0.tgz').write_bytes(data)
            records = capture.archives(None, index)
            self.assertEqual(fetched, ['1.0.0'])
            self.assertEqual(records[0]['manifest_sha256'],
                             hashlib.sha256(manifest).hexdigest())
            self.assertNotIn('manifest_sha256', records[1])
            # A manifest naming other bytes is fetched again as well.
            fetched.clear()
            archive.with_name('redis-1.0.0.manifest.json').write_bytes(
                manifest_naming('0' * 64))
            capture.archives(None, index)
            self.assertEqual(fetched, ['1.0.0'])
            # A whole capture moves nothing.
            fetched.clear()
            self.assertEqual(capture.archives(None, index), records)
            self.assertEqual(fetched, [])


if __name__ == '__main__':
    unittest.main()
