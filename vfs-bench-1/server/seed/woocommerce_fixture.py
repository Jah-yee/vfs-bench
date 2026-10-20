"""Restore one original WooCommerce seed into independent service instances."""
import gzip
import hashlib
import json
import shlex
from pathlib import Path

import requests

from server.seed.kubernetes import command

REPO = Path(__file__).resolve().parents[2]

# These are the files written by each original preprocessor, outside /work.
PRIVATE_FILES = {
    'woocommerce-customer-survey':
    ['groundtruth_workspace', 'preprocess/completed_orders.json'],
    'woocommerce-product-recall':
    ['recalled_products_info.json', 'test_customers_info.json'],
    'woocommerce-stock-alert': ['files'],
    'update-material-inventory': [
        'groundtruth_workspace', 'preprocess/test_orders.json',
        'initial_workspace/config.json'
    ],
    'woocommerce-update-cover': ['groundtruth_workspace'],
    'filter-low-selling-products': ['groundtruth_workspace'],
}


def folder(task):
    return REPO / 'task/toolathlon' / task / 'shared/fixtures/woocommerce'


def api_state(task):
    """Read complete service objects, including every page and variation."""
    from server.seed.business import tokens
    identity = tokens(task)
    session = requests.Session()
    session.auth = (identity.woocommerce_api_key,
                    identity.woocommerce_api_secret)
    base = identity.woocommerce_site_url.rstrip('/') + '/wp-json/wc/v3/'

    def listing(path):
        rows = []
        page = 1
        while True:
            response = session.get(base + path,
                                   params={
                                       'per_page': 100,
                                       'page': page
                                   },
                                   timeout=60)
            response.raise_for_status()
            batch = response.json()
            rows.extend(batch)
            if page >= int(response.headers['X-WP-TotalPages'] or 1):
                return rows
            page += 1

    try:
        objects = {
            path: listing(path)
            for path in ('products', 'orders', 'customers',
                         'products/categories')
        }
        for product in objects['products']:
            if product['type'] == 'variable':
                path = f"products/{product['id']}/variations"
                objects[path] = listing(path)
        return objects
    finally:
        session.close()


def scheduled(row):
    # A sale window is stored data; whether the clock is inside it is not.
    # WooCommerce derives on_sale and price_html from the dates on every
    # request, and its scheduled-sales cron rewrites price when a window
    # opens or closes, so a capture taken inside one stops matching the day
    # it ends. Compare the window and leave the clock out.
    if not (row.get('date_on_sale_from') or row.get('date_on_sale_to')):
        return row
    return {
        key: value
        for key, value in row.items()
        if key not in ('on_sale', 'price_html', 'price')
    }


def state_hashes(objects, sampled_related_ids=False):
    result = {}
    for path, rows in objects.items():
        if path == 'products' or path.endswith('/variations'):
            rows = [scheduled(row) for row in rows]
        # WooCommerce's wc_get_related_products shuffles this list on every
        # request. Normalize only the comparison; leave service data intact.
        if path == 'products':
            if sampled_related_ids:
                # wc_get_related_products shuffles a larger candidate pool
                # before slicing it. Large stores vary membership as well.
                rows = [{
                    key: value
                    for key, value in row.items() if key != 'related_ids'
                } for row in rows]
            else:
                rows = [{
                    **row, 'related_ids': sorted(row['related_ids'])
                } if 'related_ids' in row else row for row in rows]
        result[path] = hashlib.sha256(
            json.dumps(rows, sort_keys=True,
                       separators=(',', ':')).encode()).hexdigest()
    return result


def capture(box, task, record):
    """Save the upstream seed with its private grader data."""
    destination = folder(task)
    if destination.exists():
        raise FileExistsError(
            'Refusing to replace an existing fixture capture')
    objects = api_state(task)
    hashes = state_hashes(objects, sampled_related_ids=True)
    command(
        box, "sudo docker exec woo-db sh -c 'MYSQL_PWD=\"$MYSQL_PASSWORD\" "
        'exec mysqldump --user="$MYSQL_USER" --single-transaction '
        '--no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"\' '
        '> /tmp/woocommerce.sql')
    command(
        box, 'sudo docker exec woo-wp tar -czf /tmp/uploads.tar.gz '
        '-C /var/www/html/wp-content uploads && '
        'sudo docker cp woo-wp:/tmp/uploads.tar.gz /tmp/uploads.tar.gz && '
        'sudo chmod 644 /tmp/uploads.tar.gz')
    command(
        box, 'tar -czf /tmp/groundtruth.tar.gz -C ' +
        shlex.quote('/opt/toolathlon/tasks/finalpool/' + task) + ' ' +
        shlex.join(PRIVATE_FILES[task]))
    # transfer_out has already created the seed's workspace archive.
    data = {
        'api.json.gz':
        gzip.compress(json.dumps(objects).encode(), mtime=0),
        'database.sql.gz':
        gzip.compress(box.files.read('/tmp/woocommerce.sql', format='bytes'),
                      mtime=0),
        'uploads.tar.gz':
        box.files.read('/tmp/uploads.tar.gz', format='bytes'),
        'groundtruth.tar.gz':
        box.files.read('/tmp/groundtruth.tar.gz', format='bytes'),
        'workspace.tar.gz':
        box.files.read('/tmp/workspace.tar.gz', format='bytes'),
    }
    if record.get('bigquery'):
        from server.seed import business_bigquery
        data['bigquery.json.gz'] = business_bigquery.capture(box)
    if record.get('sheets'):
        from server.seed import business_sheets
        data['sheets.db.gz'] = business_sheets.database(box, 'capture')
        data['sheet-formats.json'] = box.files.read(
            '/tmp/toolathlon-sheet-formats.json', format='bytes')
        data['sheets-api.json.gz'] = gzip.compress(json.dumps(
            business_sheets.state()).encode(),
                                                   mtime=0)
    after = api_state(task)
    if state_hashes(after, sampled_related_ids=True) != hashes:
        evidence = (REPO / 'state/business' /
                    f'{box.sandbox_id}-capture.json.gz')
        evidence.write_bytes(
            gzip.compress(json.dumps({
                'before': objects,
                'after': after
            }).encode(),
                          mtime=0))
        raise ValueError('WooCommerce changed while its fixture was captured')
    destination.mkdir(parents=True)
    for name, content in data.items():
        (destination / name).write_bytes(content)
    source = {
        'task':
        task,
        'service':
        record,
        'api_sha256':
        hashes,
        'sampled_related_ids':
        True,
        'api_comparison':
        'All fields except related_ids, which WooCommerce '
        'randomly samples on every read. Responses are unchanged. Categories '
        'and tags determining the candidates are checked.',
        'sha256': {
            name: hashlib.sha256(content).hexdigest()
            for name, content in data.items()
        },
    }
    (destination /
     'source.json').write_text(json.dumps(source, indent=2) + '\n')
    return source


def restore(box, task, inputs):
    """Fail on source drift before making the captured state agent-visible."""
    base = folder(task)
    record = json.loads((base / 'source.json').read_text())
    if record['task'] != task or record['service']['inputs_sha256'] != inputs:
        raise ValueError(
            'Original WooCommerce sources differ from the capture')
    dependencies = json.loads(
        (REPO / 'server/business-sources.json').read_text())
    if record['service']['dependency_sources'] != dependencies:
        raise ValueError(
            'WooCommerce service dependencies differ from capture')
    for name, expected in record['sha256'].items():
        data = (base / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('WooCommerce fixture checksum mismatch: ' + name)
        if name != 'api.json.gz':
            box.files.write('/tmp/' + name, data, user='root')
    command(
        box,
        'gzip -dc /tmp/database.sql.gz | sudo docker exec -i woo-db sh -c '
        "'MYSQL_PWD=\"$MYSQL_PASSWORD\" exec mysql --user=\"$MYSQL_USER\" "
        '"$MYSQL_DATABASE"\'')
    command(
        box, 'sudo docker cp /tmp/uploads.tar.gz '
        'woo-wp:/tmp/fixture-uploads.tar.gz && '
        'sudo docker exec woo-wp sh -c '
        "'rm -rf /var/www/html/wp-content/uploads && "
        'tar -xzf /tmp/fixture-uploads.tar.gz -C /var/www/html/wp-content && '
        "chown -R www-data:www-data /var/www/html/wp-content/uploads'")
    command(
        box, 'sudo tar -xzf /tmp/groundtruth.tar.gz -C ' +
        shlex.quote('/opt/toolathlon/tasks/finalpool/' + task) +
        ' && sudo find /work -mindepth 1 -delete && '
        'sudo tar -xzf /tmp/workspace.tar.gz -C /work && '
        'sudo chown -R user:user /work')
    if 'bigquery.json.gz' in record['sha256']:
        from server.seed import business_bigquery
        business_bigquery.restore(box,
                                  (base / 'bigquery.json.gz').read_bytes())
    if 'sheets.db.gz' in record['sha256']:
        from server.seed import business_sheets
        business_sheets.database(box, 'restore',
                                 (base / 'sheets.db.gz').read_bytes())
        box.files.write('/tmp/toolathlon-sheet-formats.json',
                        (base / 'sheet-formats.json').read_bytes(),
                        user='root')
        expected = json.loads(
            gzip.decompress((base / 'sheets-api.json.gz').read_bytes()))
        if not business_sheets.matches_capture(business_sheets.state(),
                                               expected):
            raise ValueError('Restored Sheets API differs from the capture')
    return record
