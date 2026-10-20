"""Live MCP and VFS checks against the original service graders."""
import io
import json
import os
import re
import shlex
import sys
import tempfile
import unittest
from contextlib import AsyncExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
for directory in ('', 'agent', 'task', 'tests', 'server/mcp'):
    sys.path.insert(0, str(REPO / directory))

import arms  # noqa: E402
import dataset  # noqa: E402
import parity  # noqa: E402
from workspace import Workspace, config_for  # noqa: E402

from server.seed.business import TASKS, grade, serve  # noqa: E402


async def call(session, name, **args):
    result = await session.call_tool(name, args)
    text = '\n'.join(c.text for c in result.content
                     if getattr(c, 'text', None))
    if result.isError:
        raise AssertionError(f'{name}: {text}')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # The original Woo server removes backslashes from its text output.
        # Keep those bytes; mutation checks read the persisted API state.
        return text


def cli(ws, name, command, **arguments):
    text = ws.execute(name + ' ' + command + ' ' +
                      shlex.quote(json.dumps(arguments)))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Preserve the original Woo handler's text, as call() does for MCP.
        return text


@unittest.skipUnless(os.environ.get('E2B_API_KEY'),
                     'live test requires E2B_API_KEY')
class BusinessTasks(unittest.IsolatedAsyncioTestCase):

    async def run_task(self, name, solve):
        dataset.use('toolathlon')
        task = dataset.local(name)
        with tempfile.TemporaryDirectory() as work, patch.dict(
                os.environ, AGENT_WORKSPACE=work):
            arms.mirage_env(task)
            arms.build_workspace_dir(task)
            # The dataset's own services seam, which `arms.open_services`
            # and `tests/parity.py` both enter: it brings the sandbox up
            # *and* publishes the endpoints this task's tool-command CLIs
            # are pointed at. Entering `business.serve` directly starts the
            # services but leaves `${SHEETS_CLI_URL}` and its kind
            # unresolved, so a task whose yaml names one cannot build a
            # workspace at all.
            with dataset.services(name, work) as record:
                async with AsyncExitStack() as stack:
                    mcp = await parity.open_session(stack, record['service'],
                                                    task)
                    ws = Workspace.create(config_for(task))
                    stack.callback(ws.close)

                    async def session(server):
                        """A second original server beside the task's own.

                        `record['service']` names the one the fixture is
                        of, which is the one a grader reads back. A task
                        whose ask spans two -- a sheet and a mailbox, a
                        form and a mailbox -- needs the other opened too,
                        and its tools live nowhere else.
                        """
                        return await parity.open_session(stack, server, task)

                    await solve(ws, mcp, Path(work), session)
                    self.assertEqual(grade(name, work, ''), 0)
                    print(name + ': MCP + VFS + original grader PASS',
                          flush=True)

    async def reject_untouched(self, name):
        """The original grader must refuse state no arm has touched.

        `run_task` proves a grader accepts a solved fixture. That alone
        cannot tell a grader that reads service state from one that reads
        nothing and passes: both look like a pass. This is the other half
        -- seed the task, hand the untouched fixture to upstream's own
        evaluator inside the live sandbox, and require a refusal.

        Args:
            name (str): the task name.
        """
        dataset.use('toolathlon')
        task = dataset.local(name)
        with tempfile.TemporaryDirectory() as work, patch.dict(
                os.environ, AGENT_WORKSPACE=work):
            arms.mirage_env(task)
            arms.build_workspace_dir(task)
            with serve(name, work):
                printed = io.StringIO()
                with redirect_stdout(printed):
                    code = grade(name, work, '')
                spoke = printed.getvalue()
            print(spoke, flush=True)
            self.assertNotEqual(
                code, 0,
                name + ': the original grader accepted state no arm had '
                'touched')
            # A non-zero exit on its own is not a refusal: `grade` returns
            # the evaluator's exit code, and a crash, a missing config or a
            # sandbox that never came up all leave one behind. Require the
            # evaluator to have reached a verdict of its own, so that an
            # infrastructure failure cannot pass for judgement. The wording
            # is each task's -- `EVALUATION FAILED` for the commerce four,
            # a crossed box for most of the Canvas ones -- so what is
            # required is a reported failure, not one sentence.
            self.assertTrue(spoke.strip(),
                            name + ': the evaluator produced no output at all')
            # Not "no traceback": `woocommerce-update-cover` reports its
            # verdict by raising it (`evaluation/main.py:216`), so a
            # traceback there is the judgement. What must be absent is the
            # transport giving out, which is the way an unread fixture
            # still exits non-zero.
            for signature in ('pyqwest.', 'ConnectError',
                              'ConnectionRefusedError', 'Connection refused',
                              'Max retries exceeded'):
                self.assertNotIn(
                    signature, spoke, name + ': the sandbox transport failed '
                    '(' + signature + '), so nothing was graded')
            self.assertTrue(
                re.search(r'FAILED|failed|\u274c', spoke),
                name + ': exit was non-zero but nothing reported a failed '
                'check, so the refusal is not the grader\'s')
            print(name + ': original grader rejects untouched state',
                  flush=True)

    async def test_sandbox_graders_read_service_state(self):
        """Every grader that reads live services discriminates.

        These are the tasks graded against WooCommerce, Canvas, Sheets,
        Forms and the mail server rather than against files, so the
        workspace-backed smoke checks cannot reach them: the grader only
        runs inside `business.serve`, which is where the services exist
        (`business.py:427` refuses to grade a fixture that is not live).

        Taken from `business.TASKS` rather than listed here, so a task
        added to that map is covered rather than quietly left out.
        """
        for name in sorted(TASKS):
            with self.subTest(task=name):
                await self.reject_untouched(name)

    async def test_inventory_sync(self):

        async def solve(ws, mcp, work, session):
            # SQLite is read through the actual agent runtime and shared mount.
            script = '''import sqlite3,glob,json
rows=[]
for path in glob.glob('/workspace/warehouse/*.db'):
 db=sqlite3.connect(path)
 rows.extend(db.execute('SELECT w.region,i.product_id,i.quantity '
                        'FROM inventory i JOIN warehouses w '
                        'ON w.warehouse_id=i.warehouse_id').fetchall())
 db.close()
print(json.dumps(rows))'''
            rows = json.loads(ws.execute('python3 -c ' + shlex.quote(script)))
            self.assertTrue(rows)
            totals = {}
            for region, product, quantity in rows:
                totals[region, product] = totals.get(
                    (region, product), 0) + quantity
            self.assertTrue(
                cli(ws, 'woocommerce', 'products_list', perPage=100, page=1))
            # The original Woo tool strips JSON escapes. Read API objects
            # through the mount for this grader-connectivity check.
            products = [
                json.loads(
                    ws.execute('cat ' + shlex.quote('/woo/products/' +
                                                    Path(name).name)))
                for name in ws.execute('ls /woo/products').splitlines()
                if name.endswith('.json')
            ]
            touched = 0
            for product in products:
                meta = {
                    entry['key']: entry['value']
                    for entry in product['meta_data']
                }
                key = meta.get('region'), meta.get('original_product_id')
                if key not in totals:
                    continue
                path = f"/woo/products/{product['id']}.json"
                self.assertEqual(
                    json.loads(ws.execute('cat ' + path))['sku'],
                    product['sku'])
                body = {'stock_quantity': totals[key], 'manage_stock': True}
                if touched % 2:
                    await call(mcp,
                               'woo_products_update',
                               productId=product['id'],
                               productData=body)
                else:
                    cli(ws,
                        'woocommerce',
                        'products_update',
                        productId=product['id'],
                        productData=body)
                self.assertEqual(
                    json.loads(ws.execute('cat ' + path))['stock_quantity'],
                    totals[key])
                touched += 1
            self.assertEqual(touched, len(totals))

        await self.run_task('inventory-sync', solve)

    async def test_update_material_inventory(self):
        """The original grader accepts a fixture solved from its own inputs.

        The recipe and the stock on hand are read out of the sheet and the
        ordered quantities out of WooCommerce, and what is written back is
        what those imply. Upstream's `expected_results.json` is never read:
        a check that copied the expected answers in would pass whether or
        not the grader looked at the services at all.
        """

        async def solve(ws, mcp, work, session):
            spreadsheet = json.loads(
                (work / 'config.json').read_text())['spreadsheet_id']

            def values(tab):
                return cli(ws,
                           'google-sheet',
                           'get_sheet_data',
                           spreadsheet_id=spreadsheet,
                           sheet=tab)['valueRanges'][0]['values']

            rows = values('BOM')
            head = [str(cell).strip() for cell in rows[0]]
            sku_at = head.index('Product SKU')
            material_at = head.index('Raw Material ID')
            per_at = head.index('Unit Quantity')
            recipe = {}
            for row in rows[1:]:
                if len(row) > max(sku_at, material_at, per_at) and row[sku_at]:
                    recipe.setdefault(
                        row[sku_at], {})[row[material_at]] = float(row[per_at])
            self.assertTrue(recipe)

            rows = values('Material_Inventory')
            head = [str(cell).strip() for cell in rows[0]]
            id_at = head.index('\u539f\u6750\u6599ID')
            quantity_at = head.index('\u5f53\u524d\u5e93\u5b58')
            listed = [row[id_at] for row in rows[1:]]
            held = {row[id_at]: float(row[quantity_at]) for row in rows[1:]}

            # API objects are read through the mount: the original Woo
            # handler strips JSON escapes, as `test_inventory_sync` notes.
            def mounted(kind):
                return [
                    json.loads(ws.execute('cat /woo/' + kind + '/' + name))
                    for name in ws.execute('ls /woo/' + kind).splitlines()
                    if name.endswith('.json')
                ]

            ordered = {}
            for record in mounted('orders'):
                if record.get('status') != 'processing':
                    continue
                for item in record['line_items']:
                    if item.get('sku'):
                        ordered[item['sku']] = ordered.get(
                            item['sku'], 0) + item['quantity']
            self.assertTrue(ordered, 'no paid orders in the fixture')

            for sku, count in ordered.items():
                for material, per in recipe.get(sku, {}).items():
                    held[material] = round(held[material] - per * count, 4)

            column = chr(ord('A') + quantity_at)
            cli(ws,
                'google-sheet',
                'update_cells',
                spreadsheet_id=spreadsheet,
                sheet='Material_Inventory',
                range=f'{column}2:{column}{len(listed) + 1}',
                data=[[held[name]] for name in listed])

            # Stock becomes what the materials left can still build.
            makeable = {
                sku: min(int(held[m] // per) for m, per in parts.items())
                for sku, parts in recipe.items()
            }
            identifier = {
                product['sku']: product['id']
                for product in mounted('products') if product.get('sku')
            }
            for index, sku in enumerate(sorted(makeable)):
                body = {'stock_quantity': makeable[sku], 'manage_stock': True}
                if index % 2:
                    await call(mcp,
                               'woo_products_update',
                               productId=identifier[sku],
                               productData=body)
                else:
                    cli(ws,
                        'woocommerce',
                        'products_update',
                        productId=identifier[sku],
                        productData=body)

        await self.run_task('update-material-inventory', solve)

    async def test_woocommerce_stock_alert(self):
        """The original grader accepts a fixture solved from its own inputs.

        Which products are low is derived from WooCommerce -- each one's
        `stock_quantity` against the `stock_threshold` in its own metadata
        -- and the supplier columns and every email field come from the
        same records. The evaluator's hardcoded `expected_new_products` is
        never read: a check that copied those in would pass whether or not
        the grader looked at the services at all.

        The surviving row is rewritten rather than appended behind. The SKU
        scan at `evaluate_updated_stock_alert.py:233` breaks on the first
        row matching, so a second `DELL-XPS-13` row would be graded against
        the stale stock the first one still holds.
        """

        async def solve(ws, mcp, work, session):
            # API objects are read through the mount, as the inventory
            # check reads them.
            def mounted(kind):
                return [
                    json.loads(ws.execute('cat /woo/' + kind + '/' + name))
                    for name in ws.execute('ls /woo/' + kind).splitlines()
                    if name.endswith('.json')
                ]

            low = []
            for product in mounted('products'):
                meta = {
                    item['key']: item['value']
                    for item in product['meta_data']
                }
                threshold = meta.get('stock_threshold')
                stock = product.get('stock_quantity')
                if threshold is None or stock is None:
                    continue
                if int(stock) < int(threshold):
                    low.append((product, int(threshold), meta['supplier']))
            self.assertTrue(
                low, 'no product in the fixture is below its threshold')

            # The copy upstream's preprocess left in the task's own Drive
            # folder. `list_spreadsheets` with no argument lists the
            # configured folder, which is that one, so the source workbook
            # the copy was taken from is not a candidate.
            found = cli(ws, 'google-sheet', 'list_spreadsheets')
            # One spreadsheet in the folder comes back as the object itself
            # rather than as a list holding it.
            if isinstance(found, dict):
                found = [found]
            spreadsheet = next(sheet['id'] for sheet in found
                               if sheet['title'] == 'stock_sheet')

            # The copied sheet is two rows tall; the grid has to grow
            # before the records will fit. Trailing blank rows are not a
            # risk: `values.get` stops at the last row holding anything, so
            # the completeness check never sees them.
            cli(ws,
                'google-sheet',
                'batch_update',
                spreadsheet_id=spreadsheet,
                requests=[{
                    'appendDimension': {
                        'sheetId': 0,
                        'dimension': 'ROWS',
                        'length': len(low)
                    }
                }])
            cli(ws,
                'google-sheet',
                'update_cells',
                spreadsheet_id=spreadsheet,
                sheet='stock_sheet',
                range=f'A2:H{len(low) + 1}',
                data=[[
                    str(product['id']), product['name'], product['sku'],
                    str(product['stock_quantity']),
                    str(threshold), supplier['name'], supplier['supplier_id'],
                    supplier['contact']
                ] for product, threshold, supplier in low])

            # One email per product, rendered from the template the task
            # hands the agent rather than from wording chosen here.
            template = (work / 'stock_alert_email_template.md').read_text()
            subject_form = template.split('## Email Subject',
                                          1)[1].strip().splitlines()[0]
            body_form = template.split('## Email Body', 1)[1].strip()
            manager = (work /
                       'purchasing_manager_email.txt').read_text().strip()
            link = 'https://docs.google.com/spreadsheets/d/' + spreadsheet
            mail = await session('emails')
            for index, (product, threshold, supplier) in enumerate(low):
                fields = {
                    'product_name': product['name'],
                    'sku': product['sku'],
                    'current_stock': product['stock_quantity'],
                    'threshold': threshold,
                    'supplier_name': supplier['name'],
                    'supplier_contact': supplier['contact'],
                    'google_sheets_link': link,
                }
                sent = {
                    'to': manager,
                    'subject': subject_form.format(**fields),
                    'body': body_form.format(**fields)
                }
                if index % 2:
                    await call(mail, 'send_email', **sent)
                else:
                    cli(ws, 'emails', 'send_email', **sent)

        await self.run_task('woocommerce-stock-alert', solve)

    async def test_woocommerce_customer_survey(self):
        """The original grader accepts a fixture solved from its own inputs.

        Who gets a questionnaire is derived from WooCommerce -- the billing
        address on every order the shop marks `completed` -- rather than
        from the expected recipients upstream keeps in its groundtruth
        workspace. The form is built from the six questions
        `form_requirement.md` lists, in its order and its option wording.
        """

        async def solve(ws, mcp, work, session):

            def mounted(kind):
                return [
                    json.loads(ws.execute('cat /woo/' + kind + '/' + name))
                    for name in ws.execute('ls /woo/' + kind).splitlines()
                    if name.endswith('.json')
                ]

            recipients = []
            for order in mounted('orders'):
                if order.get('status') != 'completed':
                    continue
                address = (order.get('billing') or {}).get('email')
                if address and address not in recipients:
                    recipients.append(address)
            self.assertTrue(recipients, 'no completed orders in the fixture')

            satisfaction = [
                'Very satisfied', 'Satisfied', 'Neutral', 'Dissatisfied',
                'Very dissatisfied'
            ]
            asked = [
                ('Please rate your overall shopping experience.',
                 ['1 star', '2 stars', '3 stars', '4 stars', '5 stars'], True),
                ('Are you satisfied with the quality of the product you '
                 'received?', satisfaction, True),
                ('Are you satisfied with the delivery service?', satisfaction,
                 True),
                ('If you contacted customer service, how would you rate the '
                 'experience?',
                 satisfaction + ['Did not contact customer service'], False),
                ('Please provide any suggestions or feedback for '
                 'improvement.', None, False),
                ('Would you be willing to recommend our store to your '
                 'friends?', [
                     'Very willing', 'Willing', 'Might', 'Not very willing',
                     'Unwilling'
                 ], True),
            ]

            # No description is sent: the original `create_form` puts one in
            # `info` at creation, which the Forms API itself does not accept
            # there, and the grader skips an empty one rather than requiring
            # any particular wording.
            forms = await session('google_forms')
            mail = await session('emails')
            form = cli(ws,
                       'google-forms',
                       'create_form',
                       title='Customer Shopping Experience Feedback Survey')
            # Added last-first, for the reason the recall check gives:
            # the original tools insert every question at the top.
            for index, (title, options,
                        required) in enumerate(reversed(asked)):
                arguments = {
                    'formId': form['formId'],
                    'questionTitle': title,
                    'required': required
                }
                if options is not None:
                    arguments['options'] = options
                tool = ('add_multiple_choice_question'
                        if options is not None else 'add_text_question')
                if index % 2:
                    await call(forms, tool, **arguments)
                else:
                    cli(ws, 'google-forms', tool, **arguments)

            # Written through `/workspace`, then read back from the
            # directory the grader reads, so a write that never reached disk
            # fails here rather than as a missing link later.
            link = form['responderUri']
            ws.execute("printf '%s' " + shlex.quote(link) +
                       ' > /workspace/drive_url.txt')
            self.assertEqual((work / 'drive_url.txt').read_text().strip(),
                             link)

            for index, address in enumerate(recipients):
                sent = {
                    'to':
                    address,
                    'subject':
                    'How was your recent order?',
                    'body':
                    'Thank you for your purchase. Please tell us about your '
                    'shopping experience: ' + link
                }
                if index % 2:
                    await call(mail, 'send_email', **sent)
                else:
                    cli(ws, 'emails', 'send_email', **sent)

        await self.run_task('woocommerce-customer-survey', solve)

    async def test_woocommerce_product_recall(self):
        """The original grader accepts a fixture solved from its own inputs.

        Which products are recalled and which customers are affected are
        both derived from WooCommerce, by the rule the task states: a SKU
        holding one of the recalled models, or a line item naming it. The
        form is built field by field from the `recall_form_template.json`
        the task hands the agent, in its order, with its types, required
        flags and choices -- the grader compares against that same file.
        """

        async def solve(ws, mcp, work, session):

            def mounted(kind):
                return [
                    json.loads(ws.execute('cat /woo/' + kind + '/' + name))
                    for name in ws.execute('ls /woo/' + kind).splitlines()
                    if name.endswith('.json')
                ]

            # `recalled_products_info.json` is the grader's copy of this and
            # is not read: the models come from the task statement, and
            # which rows carry them comes from the shop.
            models = ('smartphone model x1', )

            def recalled(sku, name):
                return (any(model in (name or '').lower() for model in models)
                        or (sku or '').lower().startswith('phone-x1-'))

            withdrawn = [
                product for product in mounted('products')
                if recalled(product.get('sku'), product.get('name'))
            ]
            self.assertTrue(withdrawn, 'no recalled model in the catalogue')

            # One notice per recalled purchase rather than per customer.
            # A notice names a model, a product id, an order number and a
            # purchase date, and those four have to describe the same
            # purchase: the fixture sells three variants of the model, and
            # one customer bought two of them. Upstream counts the
            # customers reached rather than the notices sent, so a second
            # notice to the same address costs nothing and a notice naming
            # the wrong phone would be wrong whether or not it is graded.
            affected = []
            for order in mounted('orders'):
                billing = order.get('billing') or {}
                if not billing.get('email'):
                    continue
                for item in order.get('line_items', []):
                    if not recalled(item.get('sku'), item.get('name')):
                        continue
                    affected.append({
                        'email':
                        billing['email'],
                        'name': (billing.get('first_name', '') + ' ' +
                                 billing.get('last_name', '')).strip(),
                        'number':
                        order.get('number'),
                        'date': (order.get('date_created') or '')[:10],
                        'model':
                        item.get('name'),
                        'product':
                        str(item.get('product_id')),
                    })
            self.assertTrue(affected, 'no order carries a recalled model')
            # Each notice must carry its own purchase, not the first one
            # found, which is only visible where the variants differ.
            self.assertEqual(
                len({notice['model']
                     for notice in affected}), len(withdrawn),
                'the notices do not cover every recalled variant')

            # Off the shelf rather than deleted, which the task says
            # explicitly and the grader checks by status.
            for index, product in enumerate(withdrawn):
                body = {'status': 'draft'}
                if index % 2:
                    await call(mcp,
                               'woo_products_update',
                               productId=product['id'],
                               productData=body)
                else:
                    cli(ws,
                        'woocommerce',
                        'products_update',
                        productId=product['id'],
                        productData=body)

            template = json.loads(
                (work / 'recall_form_template.json').read_text())
            forms = await session('google_forms')
            mail = await session('emails')
            form = cli(ws,
                       'google-forms',
                       'create_form',
                       title=template['form_title'])
            # Added last-first. Both add-question tools insert at
            # `location: {index: 0}` (`vendor/forms-mcp/src/src/index.ts`
            # 277 and 344), so each new question lands above the one
            # before it and only the reverse order leaves the form in the
            # template's -- which is what the grader compares against,
            # field by field.
            for index, field in enumerate(reversed(template['fields'])):
                arguments = {
                    'formId': form['formId'],
                    'questionTitle': field['name'],
                    'required': field['required']
                }
                if field['type'] == 'choice':
                    arguments['options'] = field['choices']
                    tool = 'add_multiple_choice_question'
                else:
                    tool = 'add_text_question'
                if index % 2:
                    await call(forms, tool, **arguments)
                else:
                    cli(ws, 'google-forms', tool, **arguments)

            report = json.dumps({
                'form_id': form['formId'],
                'form_url': form['responderUri']
            })
            ws.execute("printf '%s' " + shlex.quote(report) +
                       ' > /workspace/recall_report.json')
            self.assertEqual(
                json.loads((work / 'recall_report.json').read_text()),
                json.loads(report))

            # The notice is the task's own template with its bracketed
            # placeholders filled, not wording invented here.
            notice = (work / 'recall_email_template.md').read_text()
            for index, customer in enumerate(affected):
                body = notice
                for placeholder, value in (
                    ('[Customer Name]', customer['name']),
                    ('[Product Model]', customer['model']),
                    ('[Product ID]', customer['product']),
                    ('[Order Number]', str(customer['number'])),
                    ('[Purchase Date]', customer['date']),
                    ('[Google Forms Link]', form['responderUri']),
                ):
                    body = body.replace(placeholder, value)
                sent = {
                    'to': customer['email'],
                    'subject': 'Product Recall Notice — ' + customer['model'],
                    'body': body
                }
                if index % 2:
                    await call(mail, 'send_email', **sent)
                else:
                    cli(ws, 'emails', 'send_email', **sent)

        await self.run_task('woocommerce-product-recall', solve)

    async def test_canvas_art_quiz(self):

        async def solve(ws, mcp, work, session):
            courses = cli(ws, 'canvas', 'list_courses')
            course = next(c for c in courses if 'AH101' in c['course_code'])
            course_id = course['id']
            title = 'Classic Art History Questions'
            quiz = await call(mcp,
                              'canvas_create_quiz',
                              course_id=course_id,
                              title=title)
            text = (dataset.local('canvas-art-quiz') /
                    'shared/task.md').read_text()
            blocks = re.findall(r'\n\d+\. (.+?)(?=\n\d+\. |\Z)', text, re.S)
            self.assertEqual(len(blocks), 4)
            for index, block in enumerate(blocks):
                question, *answers = re.split(r'\n\s*[ABCD]\. ', block.strip())
                body = {
                    'question_name':
                    f'Question {index + 1}',
                    'question_text':
                    question,
                    'question_type':
                    'multiple_choice_question',
                    'points_possible':
                    1,
                    'position':
                    index + 1,
                    'answers': [{
                        'text':
                        answer.strip(),
                        'weight':
                        100 if i == (1 if index < 3 else 0) else 0
                    } for i, answer in enumerate(answers)]
                }
                if index % 2:
                    await call(mcp,
                               'canvas_create_quiz_question',
                               course_id=course_id,
                               quiz_id=quiz['id'],
                               **body)
                else:
                    cli(ws,
                        'canvas',
                        'create_quiz_question',
                        course_id=course_id,
                        quiz_id=quiz['id'],
                        **body)
            questions = cli(ws,
                            'canvas',
                            'list_quiz_questions',
                            course_id=course_id,
                            quiz_id=quiz['id'])
            self.assertEqual(len(questions), 4)
            path = (f"/canvas/courses/{course_id}/quizzes/"
                    f"{quiz['id']}/questions")
            self.assertEqual(
                len([
                    p for p in ws.execute('ls ' + path).splitlines()
                    if p.endswith('.json')
                ]), 4)

        await self.run_task('canvas-art-quiz', solve)


if __name__ == '__main__':
    unittest.main()
