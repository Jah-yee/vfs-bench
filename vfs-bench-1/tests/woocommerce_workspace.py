"""Original Woo tools and VFS reads share one local REST fixture."""
import json
import os
import re
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
for directory in ('', 'agent', 'task'):
    sys.path.insert(0, str(REPO / directory))

from workspace import Workspace  # noqa: E402

from server.seed.travel_video import serve_tools  # noqa: E402


class WooWorkspace(unittest.TestCase):

    def test_original_tools_and_mounted_resources(self):
        product = {
            'id': 1,
            'name': 'Local fixture',
            'stock_quantity': 12,
            'type': 'variable'
        }
        resources = {
            'products/1': product,
            'products/1/variations/2': {
                'id': 2,
                'stock_quantity': 3
            },
            'orders/1': {
                'id': 1,
                'status': 'processing',
                'line_items': []
            },
            'customers/1': {
                'id': 1,
                'email': 'fixture@example.invalid'
            },
            'products/categories/1': {
                'id': 1,
                'name': 'Test category'
            },
        }

        class Handler(BaseHTTPRequestHandler):

            def log_message(self, *args):
                pass

            def do_GET(self):
                self.reply()

            def do_PUT(self):
                self.reply()

            def reply(self):
                path = urlparse(self.path).path.removeprefix('/wp-json/wc/v3/')
                if path in resources:
                    body = resources[path]
                    if self.command == 'PUT':
                        body.update(
                            json.loads(
                                self.rfile.read(
                                    int(self.headers['Content-Length']))))
                else:
                    body = [
                        v for k, v in resources.items()
                        if k.rsplit('/', 1)[0] == path
                    ]
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('X-WP-TotalPages', '1')
                self.end_headers()
                self.wfile.write(data)

        with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            self.addCleanup(server.shutdown)
            with tempfile.TemporaryDirectory() as tmp:
                config = REPO / ('task/toolathlon/update-material-inventory/'
                                 'vfs/workspace.yaml')
                env = {
                    key: 'http://127.0.0.1:1'
                    for key in re.findall(r'\$\{(\w+)\}', config.read_text())
                }
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    port = str(sock.getsockname()[1])
                base = f'http://127.0.0.1:{server.server_port}'
                env.update(AGENT_WORKSPACE=tmp,
                           STACK_DIR=tmp + '/stack',
                           MIRAGE_DAEMON_PORT=port,
                           TOOLATHLON_PYTHON=str(REPO /
                                                 'vendor/toolathlon-python'),
                           WORDPRESS_SITE_URL=base,
                           WOOCOMMERCE_API_BASE=base + '/wp-json/wc/v3',
                           WOOCOMMERCE_CONSUMER_KEY='fixture',
                           WOOCOMMERCE_CONSUMER_SECRET='fixture')
                with patch.dict(os.environ,
                                env), serve_tools(['woocommerce'], tmp,
                                                  'update-material-inventory'):
                    ws = Workspace.create(config)
                    try:
                        tools = json.loads(
                            (REPO / 'vendor/woocommerce-mcp/tools.json'
                             ).read_text())['tools']
                        for tool in tools:
                            name = tool['name'].removeprefix('woo_')
                            self.assertEqual(
                                json.loads(
                                    ws.execute(f'woocommerce {name} --help')),
                                {
                                    **tool, 'name': name
                                })
                        for path, expected in resources.items():
                            virtual = path.replace('products/categories/',
                                                   'categories/')
                            self.assertEqual(
                                json.loads(
                                    ws.execute(f'cat /woo/{virtual}.json')),
                                expected)
                        self.assertIn('1.json', ws.execute('ls /woo/products'))
                        self.assertNotEqual(
                            ws.execute_result(
                                'echo invalid > /woo/products/1.json')
                            ['exit_code'], 0)
                        result = ws.execute_result("""python3 - <<'PYTHON'
import json
with open('/woo/products/1.json') as source:
    assert json.load(source)['stock_quantity'] == 12
print('WOO_PYTHON_OK')
PYTHON""")
                        self.assertEqual(result['exit_code'], 0, result)
                        self.assertIn('WOO_PYTHON_OK', result['stdout'])
                        # Pyodide stages writes until command completion.
                        result = ws.execute_result(
                            'python3 -c "from pathlib import Path; '
                            "Path('/woo/products/1.json').write_text('{}')\"")
                        self.assertNotEqual(result['exit_code'], 0, result)
                        self.assertEqual(product['stock_quantity'], 12)
                        result = ws.execute_result(
                            'woocommerce products_update '
                            "'{\"productId\":1,"
                            '\"productData\":{\"stock_quantity\":7}}\'')
                        self.assertEqual(result['exit_code'], 0, result)
                        self.assertEqual(product['stock_quantity'], 7)
                        self.assertEqual(
                            json.loads(ws.execute('cat /woo/products/1.json'))
                            ['stock_quantity'], 7)
                    finally:
                        ws.close()


if __name__ == '__main__':
    unittest.main()
