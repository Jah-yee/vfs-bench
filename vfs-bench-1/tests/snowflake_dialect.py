import datetime
import json
import socket
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server.clients import snowflake  # noqa: E402


def fixture_postgres():
    """Whether the fixture cluster the shim answers from is listening."""
    parts = snowflake.dsn_parts()
    try:
        socket.create_connection((parts['host'], parts['port']), 1).close()
    except OSError:
        return False
    return True


class Rewrite(unittest.TestCase):

    def test_current_date_loses_its_parentheses(self):
        self.assertEqual(
            snowflake.rewrite('SELECT * FROM DB.PUBLIC.T WHERE DDL < '
                              'CURRENT_DATE() AND DONE = FALSE'),
            'SELECT * FROM DB.PUBLIC.T WHERE DDL < CURRENT_DATE '
            'AND DONE = FALSE')
        self.assertEqual(snowflake.rewrite('SELECT current_date ( ) AS D'),
                         'SELECT CURRENT_DATE AS D')

    def test_bare_select_keeps_snowflake_label(self):
        for query, expected in [
            ('SELECT CURRENT_DATE()',
             'SELECT CURRENT_DATE AS "CURRENT_DATE()"'),
            ('select current_date();',
             'SELECT CURRENT_DATE AS "CURRENT_DATE()"'),
            ('SELECT CURRENT_TIMESTAMP()',
             'SELECT CURRENT_TIMESTAMP AS "CURRENT_TIMESTAMP()"'),
        ]:
            with self.subTest(query=query):
                self.assertEqual(snowflake.rewrite(query), expected)

    def test_literals_and_comments_are_left_alone(self):
        query = "SELECT 'CURRENT_DATE()' AS S -- CURRENT_DATE()"
        self.assertEqual(snowflake.rewrite(query), query)

    def test_quoted_identifiers_are_names_not_calls(self):
        # Folded like any upper-case quoted name, and never rewritten.
        self.assertEqual(snowflake.rewrite('SELECT "CURRENT_DATE()" FROM T'),
                         'SELECT "current_date()" FROM T')
        self.assertEqual(
            snowflake.rewrite('CREATE TABLE T ("NUMBER" NUMBER, '
                              '"SYSDATE()" TIMESTAMP DEFAULT SYSDATE())'),
            'CREATE TABLE T ("number" NUMERIC, "sysdate()" TIMESTAMP '
            "DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'))")

    def test_a_database_before_information_schema_comes_off_either_way(self):
        # Left in front of the rewritten view, the quoted database is
        # answered `syntax error at or near "("`.
        query = ('SELECT COLUMN_NAME FROM "TRAVEL_EXPENSE_REIMBURSEMENT"'
                 ".INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'PUBLIC'")
        self.assertEqual(snowflake.database_in(query),
                         'travel_expense_reimbursement')
        self.assertTrue(
            snowflake.rewrite(query).startswith(
                'SELECT COLUMN_NAME FROM (SELECT c.*, col_description('))
        for query in [
                'SELECT * FROM "D".INFORMATION_SCHEMA.TABLES',
                'SELECT * FROM D.INFORMATION_SCHEMA.SCHEMATA',
                'SELECT * FROM INFORMATION_SCHEMA.COLUMNS',
                'SELECT * FROM "D".INFORMATION_SCHEMA.DATABASES',
        ]:
            with self.subTest(query=query):
                self.assertTrue(
                    snowflake.rewrite(query).startswith(
                        'SELECT * FROM (SELECT'))

    def test_an_aliased_view_keeps_its_alias(self):
        # `AS columns c` is answered `syntax error at or near "c"`.
        for query, tail in [
            ('SELECT c.COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS c',
             ') AS c'),
            ('SELECT * FROM D.INFORMATION_SCHEMA.TABLES AS t', ') AS t'),
            ('SELECT * FROM INFORMATION_SCHEMA.SCHEMATA "S"', ') AS "s"'),
            ('SELECT * FROM INFORMATION_SCHEMA.DATABASES d', ') AS d'),
            ('SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE 1 = 1',
             ') AS tables WHERE 1 = 1'),
            ('SELECT * FROM INFORMATION_SCHEMA.COLUMNS JOIN T ON TRUE',
             ') AS columns JOIN T ON TRUE'),
        ]:
            with self.subTest(query=query):
                self.assertTrue(snowflake.rewrite(query).endswith(tail))

    def test_every_catalog_literal_is_folded(self):
        # Unfolded, `TABLE_NAME IN (...)` gets no rows.
        for written, sent in [
            ("TABLE_NAME IN ('INVOICES', 'INVOICE_PAYMENTS')",
             "TABLE_NAME IN ('invoices', 'invoice_payments')"),
            ("t.TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')",
             "t.TABLE_SCHEMA NOT IN ('information_schema')"),
            ("TABLE_NAME IN ('INVOICES', NULL)",
             "TABLE_NAME IN ('invoices', NULL)"),
            ("TABLE_NAME IN (NULL, 'INVOICES')",
             "TABLE_NAME IN (NULL, 'invoices')"),
            ('"TABLE_NAME" IN (\'INVOICES\')',
             '"table_name" IN (\'invoices\')'),
            ("TABLE_NAME LIKE 'INV%'", "TABLE_NAME LIKE 'inv%'"),
            ("TABLE_NAME NOT ILIKE '%PAY%'", "TABLE_NAME NOT ILIKE '%pay%'"),
            ("'PUBLIC' = t.TABLE_SCHEMA", "'public' = t.TABLE_SCHEMA"),
            ('\'INVOICES\' <> "TABLE_NAME"', '\'invoices\' <> "table_name"'),
                # A mixed-case name is kept as written, as a quoted one is.
            ("SCHEMA_NAME IN ('Mixed')", "SCHEMA_NAME IN ('Mixed')"),
            ("TABLE_NAME LIKE 'Inv%'", "TABLE_NAME LIKE 'Inv%'"),
            ("TABLE_NAME IN (SELECT 'A')", "TABLE_NAME IN (SELECT 'A')"),
            ("TABLE_NAME IN (UPPER('a'))", "TABLE_NAME IN (UPPER('a'))"),
            ("STATUS IN ('ACTIVE')", "STATUS IN ('ACTIVE')"),
        ]:
            with self.subTest(written=written):
                self.assertTrue(
                    snowflake.rewrite('SELECT 1 FROM INFORMATION_SCHEMA.TABLES'
                                      f' AS t WHERE {written}').endswith(
                                          f') AS t WHERE {sent}'))

    def test_only_code_reading_the_catalog_is_folded(self):
        for query in [
                # A user table's column may share a catalog column's name.
                "SELECT 1 FROM T WHERE TABLE_NAME IN ('WIDGET')",
                "SELECT 1 FROM T WHERE TABLE_NAME = 'WIDGET'",
                # A value is stored as written, whatever it spells.
                "SELECT $$TABLE_NAME IN ('ABC')$$ AS X FROM "
                "INFORMATION_SCHEMA.TABLES -- TABLE_NAME = 'ABC'",
        ]:
            with self.subTest(query=query):
                self.assertNotIn("'widget'", snowflake.rewrite(query))
                self.assertNotIn("'abc'", snowflake.rewrite(query))
        # An unqualified view is a catalog one in INFORMATION_SCHEMA.
        self.assertEqual(
            snowflake.rewrite("SELECT 1 FROM TABLES WHERE TABLE_NAME = 'X'",
                              'INFORMATION_SCHEMA'),
            "SELECT 1 FROM TABLES WHERE TABLE_NAME = 'x'")


class Statements(unittest.TestCase):
    """One statement a call, as Snowflake runs them."""

    def test_semicolons_count_only_between_statements(self):
        for query, count in [
            ('SELECT 1', 1),
            ('SELECT 1;\n', 1),
            ("SELECT ';' AS S, 1 AS \"A;B\" -- ; SELECT 2", 1),
            ('/* ; */ SELECT 1', 1),
            ('SELECT $$A;B$$ AS X', 1),
            ('SELECT A$$B FROM T; SELECT $$;$$', 2),
                # A `$$` or a quote inside a quoted name opens nothing.
            ('SELECT 1 AS "$$"; SELECT 2 -- $$', 2),
            ('SELECT 1 AS "it\'s"; SELECT \'x\'', 2),
            ('SELECT COUNT(*) AS INVOICE_ROWS FROM P.PUBLIC.INVOICES; '
             'SELECT COUNT(*) AS PAYMENT_ROWS FROM P.PUBLIC.PAYMENTS', 2),
            ('SELECT 1;; SELECT 2; USE DATABASE D;', 3),
        ]:
            with self.subTest(query=query):
                self.assertEqual(snowflake.statement_count(query), count)

    def test_more_than_one_is_refused_before_postgres_sees_any(self):
        # Postgres would answer two counts with the second alone.
        with self.assertRaises(ValueError) as refused:
            snowflake.run('SELECT 1; SELECT 2')
        self.assertEqual(
            str(refused.exception),
            '000008 (0A000): Actual statement count 2 did not match the '
            'desired statement count 1.')


class Catalog(unittest.TestCase):
    """Names and types as Snowflake reports them."""

    def test_catalog_values_are_cased_only_in_a_catalog_read(self):
        rows = [{
            'table_name': 'invoices',
            'schema_name': 'Mixed',
            'status': 'active'
        }]
        self.assertEqual(snowflake.present(rows, True), [{
            'TABLE_NAME': 'INVOICES',
            'SCHEMA_NAME': 'Mixed',
            'STATUS': 'active'
        }])
        self.assertEqual(snowflake.present(rows, False), [{
            'TABLE_NAME': 'invoices',
            'SCHEMA_NAME': 'Mixed',
            'STATUS': 'active'
        }])

    def test_an_object_name_resolves_as_snowflake_resolves_it(self):
        # An unquoted part cannot start with a digit, and no name has four.
        for text, parts in [
            ('TRAVEL_EXPENSE_REIMBURSEMENT.PUBLIC."2024Q4REIMBURSEMENT"',
             ['TRAVEL_EXPENSE_REIMBURSEMENT', 'PUBLIC',
              '2024Q4REIMBURSEMENT']),
            ('p.public.invoices', ['P', 'PUBLIC', 'INVOICES']),
            ('"Mixed"', ['Mixed']),
            ('TRAVEL_EXPENSE_REIMBURSEMENT.PUBLIC.2024Q4REIMBURSEMENT', None),
            ('A.B.C.D', None),
        ]:
            with self.subTest(text=text):
                self.assertEqual(snowflake.object_name(text), parts)

    def test_types_are_snowflakes(self):
        # The data_type objects of SHOW COLUMNS's documented example.
        for shown, name, data_type in [
            ('integer', 'NUMBER(38,0)',
             '{"type":"FIXED","precision":38,"scale":0,"nullable":true}'),
            ('numeric', 'NUMBER(38,0)',
             '{"type":"FIXED","precision":38,"scale":0,"nullable":true}'),
            ('numeric(18,2)', 'NUMBER(18,2)',
             '{"type":"FIXED","precision":18,"scale":2,"nullable":true}'),
            ('text', 'VARCHAR(16777216)',
             '{"type":"TEXT","length":16777216,"byteLength":16777216,'
             '"nullable":true,"fixed":false}'),
            ('character(1)', 'VARCHAR(1)',
             '{"type":"TEXT","length":1,"byteLength":4,"nullable":true,'
             '"fixed":false}'),
            ('double precision', 'FLOAT', '{"type":"REAL","nullable":true}'),
            ('boolean', 'BOOLEAN', '{"type":"BOOLEAN","nullable":true}'),
            ('date', 'DATE', '{"type":"DATE","nullable":true}'),
            ('timestamp without time zone', 'TIMESTAMP_NTZ(9)',
             '{"type":"TIMESTAMP_NTZ","precision":0,"scale":9,'
             '"nullable":true}'),
            ('timestamp(3) with time zone', 'TIMESTAMP_TZ(3)',
             '{"type":"TIMESTAMP_TZ","precision":0,"scale":3,'
             '"nullable":true}'),
            ('time without time zone', 'TIME(9)',
             '{"type":"TIME","precision":0,"scale":9,"nullable":true}'),
        ]:
            with self.subTest(shown=shown):
                spelt, properties = snowflake.snowflake_type(shown, True)
                self.assertEqual(spelt, name)
                self.assertEqual(json.dumps(properties, separators=(',', ':')),
                                 data_type)

    def test_defaults_lose_what_postgres_added(self):
        for kept, shown in [
            ("'active'::character varying", "'active'"),
            ('0.00', '0.00'),
            ('CURRENT_TIMESTAMP', 'CURRENT_TIMESTAMP()'),
            ("(CURRENT_TIMESTAMP AT TIME ZONE 'UTC'::text)", 'SYSDATE()'),
            (None, None),
        ]:
            with self.subTest(kept=kept):
                self.assertEqual(snowflake.snowflake_default(kept), shown)


class HavingAliases(unittest.TestCase):
    """HAVING names a select-list alias, which Snowflake resolves."""

    def test_the_landing_task_reminder_query(self):
        # landing-task-reminder's own query, trimmed to two of its five
        # counts.
        query = ('SELECT e.EMPLOYEE_ID, e.NAME,\n'
                 '  COUNT(CASE WHEN pt.FINISHED_FLAG = false THEN 1 END)'
                 ' as incomplete_pub,\n'
                 '  COUNT(CASE WHEN b.FINISHED_FLAG = false THEN 1 END)'
                 ' as incomplete_backend\n'
                 'FROM L.PUBLIC.EMPLOYEE e\n'
                 'LEFT JOIN L.PUBLIC.PUBLIC_TASKS pt'
                 ' ON e.EMPLOYEE_ID = pt.EMPLOYEE_ID\n'
                 'LEFT JOIN L.PUBLIC.GROUP_TASKS_BACKEND b'
                 ' ON e.EMPLOYEE_ID = b.EMPLOYEE_ID\n'
                 'GROUP BY e.EMPLOYEE_ID, e.NAME\n'
                 'HAVING incomplete_pub > 0 OR incomplete_backend > 0;')
        self.assertTrue(
            snowflake.having_aliases(query).endswith(
                'HAVING (COUNT(CASE WHEN pt.FINISHED_FLAG = false THEN 1 END))'
                ' > 0 OR (COUNT(CASE WHEN b.FINISHED_FLAG = false THEN 1 END))'
                ' > 0;'))

    def test_names_fold_as_snowflake_folds_them(self):
        query = ('SELECT DISTINCT g, SUM(v) AS total, MAX(v) AS "Top" FROM t '
                 'GROUP BY g HAVING TOTAL > 1 AND "Top" < 9 AND top > 0 '
                 'ORDER BY total')
        self.assertEqual(
            snowflake.having_aliases(query),
            'SELECT DISTINCT g, SUM(v) AS total, MAX(v) AS "Top" FROM t '
            'GROUP BY g HAVING (SUM(v)) > 1 AND (MAX(v)) < 9 AND top > 0 '
            'ORDER BY total')

    def test_only_its_own_select_lists_aliases(self):
        for query in [
                # Qualified, a call, in a literal, or aliased without AS.
                "SELECT COUNT(*) AS n FROM t GROUP BY g "
                "HAVING t.n > 1 OR n(1) > 0 OR g = 'n'",
                'SELECT COUNT(*) n FROM t GROUP BY g HAVING n > 1',
                # The outer alias is not the subquery's.
                'SELECT COUNT(*) AS n, g FROM (SELECT g FROM t GROUP BY g '
                'HAVING n > 1) s GROUP BY g',
                # Inside a call, the name is a column: an alias for an
                # aggregate would nest it in another.
                'SELECT g, COUNT(*) AS n FROM t GROUP BY g HAVING MAX(n) > 1',
                # GROUPING takes a grouping column.
                'SELECT g, COUNT(*) AS n FROM t GROUP BY ROLLUP(g, n) '
                'HAVING GROUPING(n) = 0',
                # An aggregate's ordering is its argument too.
                'SELECT g, COUNT(*) AS n FROM t GROUP BY g HAVING '
                'PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n) > 1',
        ]:
            with self.subTest(query=query):
                self.assertEqual(snowflake.having_aliases(query), query)

    def test_a_subquery_in_having_keeps_its_own_names(self):
        self.assertEqual(
            snowflake.having_aliases(
                'SELECT g, COUNT(*) AS n FROM t GROUP BY g HAVING (n > 1 '
                'OR n < 0) AND EXISTS (SELECT n FROM u) AND n IN (SELECT n '
                'FROM v)'),
            'SELECT g, COUNT(*) AS n FROM t GROUP BY g HAVING ((COUNT(*)) > 1 '
            'OR (COUNT(*)) < 0) AND EXISTS (SELECT n FROM u) AND (COUNT(*)) '
            'IN (SELECT n FROM v)')

    def test_a_scalar_call_takes_the_alias_and_an_aggregate_does_not(self):
        self.assertEqual(
            snowflake.having_aliases(
                'SELECT COUNT(*) AS n FROM t HAVING COALESCE(n, 0) > 0 '
                'AND COALESCE(MAX(n), 0) > 1'),
            'SELECT COUNT(*) AS n FROM t HAVING COALESCE((COUNT(*)), 0) > 0 '
            'AND COALESCE(MAX(n), 0) > 1')

    def test_a_select_without_from(self):
        self.assertEqual(
            snowflake.having_aliases('SELECT COUNT(*) AS n HAVING n > 0'),
            'SELECT COUNT(*) AS n HAVING (COUNT(*)) > 0')

    def test_a_subquerys_having_reads_its_own_select(self):
        query = ('SELECT * FROM (SELECT g, COUNT(*) AS n FROM t GROUP BY g '
                 'HAVING n > 1) s WHERE s.n > 2')
        self.assertEqual(
            snowflake.having_aliases(query),
            'SELECT * FROM (SELECT g, COUNT(*) AS n FROM t GROUP BY g '
            'HAVING (COUNT(*)) > 1) s WHERE s.n > 2')


class Session(unittest.TestCase):
    """Names resolve where upstream's session resolves them."""

    def test_a_column_comment_names_its_database_only_with_four_parts(self):
        # The three-part form must not be sent to a Postgres database
        # called `public`.
        for query, database in [
            ('COMMENT ON COLUMN "PUBLIC"."INVOICE_PAYMENTS"."OUTSTANDING_FLAG"'
             " IS '0=Paid'", None),
            ('COMMENT ON COLUMN PURCHASE_INVOICE.PUBLIC.INVOICE_PAYMENTS.'
             "OUTSTANDING_FLAG IS '0=Paid'", 'purchase_invoice'),
            ("COMMENT ON TABLE PURCHASE_INVOICE.PUBLIC.T IS 'x'",
             'purchase_invoice'),
        ]:
            with self.subTest(query=query):
                self.assertEqual(snowflake.database_in(query), database)

    def test_use_names_what_it_switches_to(self):
        for query, target in [
            ('USE DATABASE purchase_invoice', ('PURCHASE_INVOICE', None)),
            ('use sla_monitor;', ('SLA_MONITOR', None)),
            ('USE SCHEMA SLA_MONITOR.PUBLIC', ('SLA_MONITOR', 'PUBLIC')),
            ('USE sla_monitor.reports', ('SLA_MONITOR', 'REPORTS')),
            ('USE DATABASE "Mixed"', ('Mixed', None)),
            ('USE SCHEMA PUBLIC', (None, 'PUBLIC')),
            ('USE SCHEMA "d"."Other"', ('d', 'Other')),
            ('USE WAREHOUSE COMPUTE_WH', None),
            ('USE ROLE ACCOUNTADMIN', None),
            ('SELECT 1', None),
        ]:
            with self.subTest(query=query):
                self.assertEqual(snowflake.used(query), target)

    def test_the_session_starts_in_upstreams_database_and_follows_use(self):
        from unittest.mock import patch

        from server.mcp import mcp_servers
        sys.path.insert(0, str(REPO / 'redirect/snowflake'))
        from snowflake.snowpark import Session as Snowpark
        task = REPO / 'task/toolathlon/payable-invoice-checker'
        with patch.object(mcp_servers, 'vendored', return_value='server'):
            args = mcp_servers.snowflake(mcp_servers.Launch(task,
                                                            '/tmp'))['args']
        flags = dict(zip(args[::2], args[1::2]))
        self.assertEqual(flags['--database'], 'SNOWFLAKE')
        self.assertEqual(flags['--schema'], 'PUBLIC')
        self.assertEqual(flags['--allowed_databases'], 'PURCHASE_INVOICE')

        def use(database, schema):
            # SNOWFLAKE's schemas are Snowflake's own; PUBLIC is not one.
            if 'MISSING' in (database, schema) or \
                    (database, schema) == ('SNOWFLAKE', 'PUBLIC'):
                raise LookupError(snowflake.MISSING_OBJECT)

        with patch.object(snowflake, 'execute', return_value=[]) as run, \
                patch.object(snowflake, 'use', side_effect=use):
            # Logging in to a schema that is not there leaves none current.
            session = Snowpark.builder.configs({
                'database': flags['--database'],
                'schema': flags['--schema']
            }).create()
            session.sql('SELECT * FROM PUBLIC.INVOICE_PAYMENTS').collect()
            session.sql('USE WAREHOUSE COMPUTE_WH')
            session.sql('SELECT 1').collect()
            session.sql('USE DATABASE PURCHASE_INVOICE').collect()
            session.sql('SELECT * FROM INVOICE_PAYMENTS').collect()
            session.sql('USE SCHEMA PURCHASE_INVOICE.ARCHIVE').collect()
            session.sql('SELECT * FROM INVOICE_PAYMENTS').collect()
            for missing in ('USE DATABASE MISSING', 'USE SCHEMA MISSING'):
                with self.assertRaisesRegex(LookupError, 'does not exist'):
                    session.sql(missing).collect()
            session.sql('SELECT * FROM INVOICE_PAYMENTS').collect()
        self.assertEqual([call.args[1:] for call in run.call_args_list],
                         [('SNOWFLAKE', None), ('SNOWFLAKE', None),
                          ('PURCHASE_INVOICE', 'PUBLIC'),
                          ('PURCHASE_INVOICE', 'ARCHIVE'),
                          ('PURCHASE_INVOICE', 'ARCHIVE')])

    def test_context_calls_answer_for_the_session(self):
        # Unanswered here, they would come back `postgres` and `public`.
        sql, labels = snowflake.session_values(
            'SELECT CURRENT_DATABASE(), current_schema( ) AS S', 'SNOWFLAKE',
            None)
        self.assertEqual(
            sql, 'SELECT (SELECT \'SNOWFLAKE\' AS "snowflake label 1"), '
            '(SELECT NULL::text AS "snowflake label 0") AS S')
        self.assertEqual(
            labels, {
                'snowflake label 0': 'CURRENT_SCHEMA( )',
                'snowflake label 1': 'CURRENT_DATABASE()'
            })
        # Compared with a catalog column, the name Postgres keeps.
        for schema, compared in [('PUBLIC', "'public'"), (None, 'NULL')]:
            with self.subTest(schema=schema):
                self.assertEqual(
                    snowflake.session_values(
                        'SELECT TABLE_NAME FROM T WHERE TABLE_SCHEMA = '
                        "CURRENT_SCHEMA() AND N = 'CURRENT_SCHEMA()'", 'D',
                        schema)[0],
                    'SELECT TABLE_NAME FROM T WHERE TABLE_SCHEMA = '
                    f"{compared} AND N = 'CURRENT_SCHEMA()'")
        # On either side, qualified or not; and SNOWFLAKE is the
        # maintenance database's catalog entry.
        for database, compared in [('SNOWFLAKE', "'postgres'"),
                                   ('PURCHASE_INVOICE', "'purchase_invoice'")]:
            with self.subTest(database=database):
                self.assertEqual(
                    snowflake.session_values(
                        'SELECT 1 FROM T WHERE CURRENT_SCHEMA() = '
                        'TABLE_SCHEMA AND CURRENT_DATABASE() <> '
                        '"T".TABLE_CATALOG', database, 'PUBLIC')[0],
                    "SELECT 1 FROM T WHERE 'public' = TABLE_SCHEMA AND "
                    f'{compared} <> "T".TABLE_CATALOG')

    def test_show_columns_filters_by_the_pattern_it_was_given(self):
        from unittest.mock import patch
        for query, like in [
            ('SHOW COLUMNS IN TABLE T', '%'),
            ("SHOW COLUMNS LIKE '' IN TABLE T", ''),
            ("SHOW COLUMNS LIKE 'O''K%' IN TABLE T", "O'K%"),
        ]:
            with self.subTest(query=query), \
                    patch.object(snowflake, 'show_columns',
                                 return_value=[]) as shown:
                self.assertEqual(snowflake.run(query), ([], 0))
                self.assertEqual(shown.call_args.args[:2], ('T', like))


@unittest.skipUnless(fixture_postgres(), 'fixture Postgres is not running')
class Answers(unittest.TestCase):

    def test_bare_current_date_answers_under_its_snowflake_label(self):
        [row] = snowflake.execute('SELECT CURRENT_DATE()')
        self.assertEqual(list(row), ['CURRENT_DATE()'])
        self.assertIsInstance(row['CURRENT_DATE()'], datetime.date)

    def test_catalog_scan_counts_only_user_tables(self):
        rows = snowflake.execute(
            'SELECT TABLE_SCHEMA, TABLE_TYPE, ROW_COUNT FROM '
            'INFORMATION_SCHEMA.TABLES')
        self.assertTrue(rows)
        for row in rows:
            if row['TABLE_SCHEMA'] in ('PG_CATALOG', 'INFORMATION_SCHEMA'):
                self.assertIsNone(row['ROW_COUNT'])
            elif row['TABLE_TYPE'] == 'BASE TABLE':
                self.assertIsInstance(row['ROW_COUNT'], int)

    def test_use_of_a_missing_database_or_schema_fails(self):
        snowflake.use('SNOWFLAKE', 'INFORMATION_SCHEMA')
        for database, schema in [('NO_SUCH_DATABASE', None),
                                 ('SNOWFLAKE', 'NO_SUCH_SCHEMA'),
                                 ('SNOWFLAKE', 'PUBLIC')]:
            with self.subTest(database=database, schema=schema):
                with self.assertRaisesRegex(LookupError, '^002043 '):
                    snowflake.use(database, schema)

    def test_having_names_a_select_alias(self):
        self.assertEqual(
            snowflake.execute(
                'SELECT g, COUNT(*) AS n FROM (VALUES (1), (1), (2)) '
                'AS t(g) GROUP BY g HAVING n > 1'), [{
                    'G': 1,
                    'N': 2
                }])

    def test_an_unqualified_name_resolves_in_the_sessions_schema(self):
        [row] = snowflake.execute('SELECT COUNT(*) AS N FROM SCHEMATA',
                                  'SNOWFLAKE', 'INFORMATION_SCHEMA')
        self.assertGreater(row['N'], 0)

    def test_context_calls_name_the_session_not_postgres(self):
        self.assertEqual(
            snowflake.execute('SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()',
                              'SNOWFLAKE', None), [{
                                  'CURRENT_DATABASE()': 'SNOWFLAKE',
                                  'CURRENT_SCHEMA()': None
                              }])
        self.assertEqual(
            snowflake.execute(
                'SELECT CURRENT_DATABASE() AS DB, CURRENT_SCHEMA() AS S',
                'SNOWFLAKE', 'INFORMATION_SCHEMA'), [{
                    'DB': 'SNOWFLAKE',
                    'S': 'INFORMATION_SCHEMA'
                }])
        [row] = snowflake.execute(
            'SELECT COUNT(*) AS N FROM INFORMATION_SCHEMA.TABLES WHERE '
            'CURRENT_DATABASE() = TABLE_CATALOG AND CURRENT_SCHEMA() = '
            'TABLE_SCHEMA', 'SNOWFLAKE', 'INFORMATION_SCHEMA')
        self.assertGreater(row['N'], 0)

    def test_a_dollar_quoted_string_is_one_value(self):
        self.assertEqual(snowflake.execute('SELECT $$A;B$$ AS X'), [{
            'X': 'A;B'
        }])

    def test_a_table_is_described_as_snowflake_describes_it(self):
        # travel-expense-reimbursement's own DDL, through the rewrite, as a
        # table only this connection sees.
        ddl = snowflake.rewrite(
            'CREATE TABLE "2024Q4REIMBURSEMENT" (ID INTEGER AUTOINCREMENT '
            'PRIMARY KEY, CLAIM_ID VARCHAR(40) UNIQUE, TRIP_START DATE, '
            'TOTAL_CLAIMED NUMBER(18,2), STATUS VARCHAR(20) NOT NULL '
            "DEFAULT 'active', FLAG INTEGER DEFAULT 0)")
        conn = snowflake.connect(None, None)
        try:
            with conn.cursor() as cur:
                cur.execute(ddl.replace('CREATE TABLE', 'CREATE TEMP TABLE'))
                cur.execute(
                    snowflake.rewrite('COMMENT ON COLUMN "2024Q4REIMBURSEMENT"'
                                      ".FLAG IS '1 = over the cap'"))
                cur.execute('SELECT \'"2024q4reimbursement"\'::regclass::oid')
                [oid] = cur.fetchone()
                self.assertEqual(
                    snowflake.table_ddl(cur, oid, False),
                    'create or replace TABLE "2024Q4REIMBURSEMENT" (\n'
                    '\tID NUMBER(38,0) NOT NULL autoincrement start 1 '
                    'increment 1 noorder,\n'
                    '\tCLAIM_ID VARCHAR(40),\n'
                    '\tTRIP_START DATE,\n'
                    '\tTOTAL_CLAIMED NUMBER(18,2),\n'
                    "\tSTATUS VARCHAR(20) NOT NULL DEFAULT 'active',\n"
                    "\tFLAG NUMBER(38,0) DEFAULT 0 COMMENT '1 = over the cap',"
                    '\n\tprimary key (ID),\n'
                    '\tunique (CLAIM_ID)\n'
                    ');')
                rows = snowflake.column_rows(cur, oid, 'id')
                self.assertEqual([list(row) for row in rows], [[
                    'table_name', 'schema_name', 'column_name', 'data_type',
                    'null?', 'default', 'kind', 'expression', 'comment',
                    'database_name', 'autoincrement', 'schema_evolution_record'
                ]])
                self.assertEqual(
                    {
                        key: rows[0][key]
                        for key in ('table_name', 'column_name', 'data_type',
                                    'null?', 'default', 'autoincrement')
                    }, {
                        'table_name': '2024Q4REIMBURSEMENT',
                        'column_name': 'ID',
                        'data_type': '{"type":"FIXED","precision":38,'
                        '"scale":0,"nullable":false}',
                        'null?': 'false',
                        'default': '',
                        'autoincrement': 'IDENTITY START 1 INCREMENT 1 NOORDER'
                    })
                self.assertEqual(
                    snowflake.column_rows(cur, oid, 'FLAG')[0]['comment'],
                    '1 = over the cap')
        finally:
            conn.close()

    def test_an_aliased_view_or_a_list_of_names_finds_the_table(self):
        # Both shapes, asked of a table only this connection sees.
        conn = snowflake.connect(None, None)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    snowflake.rewrite('CREATE TEMP TABLE INVOICES (ID INT)'))
                for query in [
                        'SELECT c.COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS'
                        " c WHERE c.TABLE_NAME IN ('INVOICES', 'PAYMENTS')",
                        'SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS '
                        "AS c WHERE c.TABLE_NAME LIKE 'INVOICE%'",
                        'SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS '
                        "WHERE 'INVOICES' = TABLE_NAME",
                        'SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS '
                        'WHERE "TABLE_NAME" IN (NULL, \'INVOICES\')',
                ]:
                    with self.subTest(query=query):
                        cur.execute(snowflake.rewrite(query))
                        self.assertEqual(cur.fetchall(), [('id', )])
        finally:
            conn.close()

    def test_a_name_that_is_not_one_or_is_missing_says_so(self):
        with self.assertRaisesRegex(
                LookupError, '^string is not a valid identifier: '
                '"D.PUBLIC.2024Q4REIMBURSEMENT"$'):
            snowflake.execute("SELECT GET_DDL('TABLE', "
                              "'D.PUBLIC.2024Q4REIMBURSEMENT') AS DDL")
        with self.assertRaisesRegex(
                LookupError, '^relation "public.no_such_table" does '
                'not exist$'):
            snowflake.execute('SHOW COLUMNS IN TABLE PUBLIC.NO_SUCH_TABLE')


if __name__ == '__main__':
    unittest.main()
