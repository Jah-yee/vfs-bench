"""Capture the original public workbook referenced by audit preprocessing."""
import hashlib
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SOURCE = 'tasks/finalpool/k8s-safety-audit/preprocess/main.py'
DEST = REPO / 'task/toolathlon/k8s-safety-audit/shared/fixtures'


def main():
    checkout = REPO / 'submodule/Toolathlon'
    script = subprocess.check_output(
        ['git', '-C', str(checkout), 'show', 'HEAD:' + SOURCE])
    sheet_id = re.search(rb'docs.google.com/spreadsheets/d/([^/]+)',
                         script).group(1).decode()
    url = (f'https://docs.google.com/spreadsheets/d/{sheet_id}/'
           'export?format=xlsx')
    data = urllib.request.urlopen(url, timeout=60).read()
    if not data.startswith(b'PK'):
        raise ValueError(
            'Original Sheet export did not return an XLSX archive')
    publish(data, url, script, checkout)


def publish(data, url, script, checkout):
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'audit.xlsx').write_bytes(data)
    (DEST / 'source.json').write_text(
        json.dumps(
            {
                'url':
                url,
                'captured_at':
                datetime.now(timezone.utc).isoformat(),
                'sha256':
                hashlib.sha256(data).hexdigest(),
                'upstream_revision':
                subprocess.check_output(
                    ['git', '-C',
                     str(checkout), 'rev-parse', 'HEAD'],
                    text=True).strip(),
                'preprocess_path':
                SOURCE,
                'preprocess_sha256':
                hashlib.sha256(script).hexdigest(),
            },
            indent=2) + '\n')


if __name__ == '__main__':
    main()
