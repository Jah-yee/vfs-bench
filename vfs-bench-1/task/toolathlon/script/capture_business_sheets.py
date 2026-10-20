"""Capture the public workbooks referenced by original task seeds."""
import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path

import openpyxl
import requests

from server.seed.kubernetes import original

REPO = Path(__file__).resolve().parents[3]
SOURCES = {
    'vlm-history-completer': '1USjrHiFIUuPQCBflwoTpe5VLEVFc2FCYbKt7JxGKGFw',
    'gdp-cr5-analysis': '10gld103ZdIZvCUFwn9-vrkgOElzI37JqYBAK5rBQt1Y',
    'llm-training-dataset': '1Vs0uhbqvUvV9r7jOBoANvD7Vy1AXzkHQMnns2zOL0Ps',
    'inter-final-performance-analysis':
    '1fKZ2b4R5kFgxGFis9UuJV2ANxth0Kdu_ifK8krlui4o',
    'woocommerce-stock-alert': '1cMNmXLps78jD-_5bYZlQRitx7mHXagInEHLWW2cBwEY',
    'update-material-inventory':
    '1S9BFFHU262CjU87DnGFfP_LMChhAT4lx7uNvwY-7HoI',
}


def capture(task):
    source = f'tasks/finalpool/{task}/preprocess/main.py'
    content = original(source)
    sheet_id = SOURCES[task]
    if not re.search(
            rb'https://docs.google.com/spreadsheets/d/' + sheet_id.encode(),
            content):
        raise ValueError('Original task references a different Sheet')
    target = REPO / 'task/toolathlon' / task / 'shared/fixtures/sheets'
    if target.exists():
        raise FileExistsError('Original Sheet capture already exists')
    url = (f'https://docs.google.com/spreadsheets/d/{sheet_id}/'
           'export?format=xlsx')
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    disposition = Message()
    disposition['Content-Disposition'] = response.headers[
        'Content-Disposition']
    filename = disposition.get_filename()
    if not filename or not filename.endswith('.xlsx'):
        raise ValueError('The source did not provide its workbook filename')
    target.mkdir(parents=True)
    path = target / 'source.xlsx'
    path.write_bytes(response.content)
    workbook = openpyxl.load_workbook(path)
    tabs = workbook.sheetnames
    workbook.close()
    record = {
        'url': url,
        'sheet_id': sheet_id,
        'title': filename[:-5],
        'tabs': tabs,
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'source': source,
        'source_sha256': hashlib.sha256(content).hexdigest(),
        'sha256': hashlib.sha256(response.content).hexdigest()
    }
    if task in ('llm-training-dataset', 'inter-final-performance-analysis',
                'vlm-history-completer'):
        # Google sanitizes export filenames, including spaces in titles.
        page_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/edit'
        page = requests.get(page_url, timeout=90)
        page.raise_for_status()
        title = re.search(r'<title>(.*?)</title>', page.text)
        if not title or not title[1].endswith(' - Google Sheets'):
            raise ValueError('The public Sheet did not provide its title')
        record['title'] = html.unescape(title[1][:-len(' - Google Sheets')])
        (target / 'source.html').write_bytes(page.content)
        record['title_source'] = {
            'url': page_url,
            'sha256': hashlib.sha256(page.content).hexdigest()
        }
    (target / 'source.json').write_text(json.dumps(record, indent=2) + '\n')
    print(task, record['title'], tabs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task', choices=SOURCES)
    capture(parser.parse_args().task)


def capture_rendering(task):
    """Retain original public numeric display strings for fixture checks."""
    folder = REPO / 'task/toolathlon' / task / 'shared/fixtures/sheets'
    source = json.loads((folder / 'source.json').read_text())
    target = folder / 'rendering.json'
    if target.exists():
        raise FileExistsError('Original rendering capture already exists')
    records = {}
    for tab in source['tabs']:
        response = requests.get('https://docs.google.com/spreadsheets/d/' +
                                source['sheet_id'] + '/gviz/tq',
                                params={
                                    'tqx': 'out:json',
                                    'sheet': tab,
                                    'headers': 0
                                },
                                timeout=90)
        response.raise_for_status()
        body = response.text
        data = json.loads(body[body.index('{'):body.rindex('}') + 1])
        if data['status'] != 'ok':
            raise ValueError('Original rendering capture failed')
        records[tab] = {
            'url': response.url,
            'body': body,
            'captured_at': datetime.now(timezone.utc).isoformat(),
            'sha256': hashlib.sha256(body.encode()).hexdigest()
        }
    target.write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    main()
