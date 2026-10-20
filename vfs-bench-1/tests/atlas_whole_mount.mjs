import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { after, before, test } from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  Workspace,
  configToWorkspaceArgs,
  loadWorkspaceConfig,
} from '../submodule/mirage/typescript/packages/node/dist/index.js'

const POLICY = fileURLToPath(new URL('../task/mcpatlas/whole_mount.py', import.meta.url))
const PROGRAM = [{ script: POLICY, runtime: 'monty' }]
const TABLE = '/airtable/bases/Sales__app1/Orders__tbl1'
const ROWS = '/notion/databases/Leads__db1/Leads__ds1/rows.jsonl'
const DOCUMENTS = '/mongodb/shop/collections/orders/documents.jsonl'
// The MCP arm's Notion tool as the shell spells it, with no session behind
// it: a line the policy lets through fails in the tool instead.
const NOTION = `${fileURLToPath(new URL('../cli/mcpatlas/tools.mjs', import.meta.url))}:NOTION`
const NO_SESSION = /^notion session is not running$/m

// Disk trees stand in for the services' mounts: the policy reads a
// command's name, its words and the paths it resolves to, never what
// serves them. Every file holds `needle`, so a command let through exits 0.
const FILES = {
  'data/sales.csv': 'needle\n',
  'repo/README.md': 'needle\n',
  'airtable/bases/Sales__app1/base.json': '{"needle": 1}\n',
  'airtable/bases/Sales__app1/Orders__tbl1/table.json': '{"needle": 1}\n',
  'airtable/bases/Sales__app1/Orders__tbl1/records.jsonl': '{"needle": 1}\n',
  'airtable/bases/Sales__app1/Orders__tbl1/views/Grid__viw1.jsonl': '{"needle": 1}\n',
  'mongodb/shop/database.json': '{"needle": 1}\n',
  'mongodb/shop/collections/orders/schema.json': '{"needle": 1}\n',
  'mongodb/shop/collections/orders/documents.jsonl': '{"needle": 1}\n',
  'notion/pages/page.md': 'needle\n',
  'notion/databases/Leads__db1/Leads__ds1/rows.jsonl': '{"needle": 1}\n',
  'slack/channels/general.jsonl': '{"needle": 1}\n',
  'calendar/events.jsonl': '{"needle": 1}\n',
}

let root
let workspace

before(async () => {
  root = mkdtempSync(join(tmpdir(), 'whole-mount-'))
  for (const [path, text] of Object.entries(FILES)) {
    mkdirSync(dirname(join(root, path)), { recursive: true })
    writeFileSync(join(root, path), text)
  }
  const disk = (dir) => ({ vfs: 'disk', config: { root: join(root, dir) } })
  // The policy as every task's vfs/workspace.yaml declares it.
  const args = await configToWorkspaceArgs(
    loadWorkspaceConfig({
      mode: 'EXEC',
      runtimes: ['workspace'],
      mounts: {
        '/tmp': { vfs: 'ram' },
        '/data': disk('data'),
        '/data/repos/demo': disk('repo'),
        '/airtable': disk('airtable'),
        '/mongodb': disk('mongodb'),
        '/notion': disk('notion'),
        '/slack': disk('slack'),
        '/calendar': disk('calendar'),
      },
      clis: { notion: { cli: NOTION, config: { apiBase: '' } } },
      profiles: { default: { policy: { pre_execute: PROGRAM, pre_command: PROGRAM } } },
    }),
  )
  workspace = new Workspace({ ...args.mounts }, args.options)
  assert.equal((await workspace.shell('echo needle > /tmp/note')).exitCode, 0)
})

after(async () => {
  await workspace.close()
  rmSync(root, { recursive: true, force: true })
})

async function run(line) {
  const result = await workspace.shell(line)
  const stderr = result.stderr
  return {
    code: result.exitCode,
    stderr: typeof stderr === 'string' ? stderr : new TextDecoder().decode(stderr),
  }
}

test('a walk that prints what it finds in a whole mount is refused', async () => {
  const refused = {
    'find /': 'find',
    "find /data -name '*.csv'": 'find',
    'find /data/repos -name README.md': 'find',
    'find /airtable/bases/Sales__app1': 'find',
    'find /mongodb/shop/collections -name schema.json': 'find',
    'tree /notion': 'tree',
    'ls -R /slack': 'ls',
    'du -a /calendar': 'du',
    'grep -rn needle /data': 'grep',
    'rg needle /mongodb/shop': 'rg',
    // A bare `grep -r` walks the working directory.
    'cd /data && grep -rn needle': 'grep',
    // Deeper than three levels, or running a command on what it finds.
    'find /data -maxdepth 4': 'find',
    'find /data -maxdepth 2 -exec cat {} +': 'find',
    'tree -L 4 /airtable': 'tree',
  }
  for (const [line, name] of Object.entries(refused)) {
    const { code, stderr } = await run(line)
    assert.notEqual(code, 0, line)
    assert.match(stderr, new RegExp(`^${name}: Permission denied$`, 'm'), line)
  }
})

test('a cat of a whole Airtable table or view, MongoDB collection, or Notion rows, is refused', async () => {
  for (const line of [`cat ${TABLE}/records.jsonl`, `cat ${TABLE}/views/Grid__viw1.jsonl`, `cat ${DOCUMENTS}`, `cat ${ROWS}`, `cat ${ROWS} | jq .needle`]) {
    const { code, stderr } = await run(line)
    assert.notEqual(code, 0, line)
    assert.match(stderr, /^cat: Permission denied$/m, line)
  }
})

test('a read of every table of a base or database at once is refused', async () => {
  for (const [line, name] of Object.entries({
    'grep needle /airtable/bases/Sales__app1/*/records.jsonl': 'grep',
    'grep -i needle /airtable/bases/Sales__app1/*/*.jsonl': 'grep',
    'cat /mongodb/shop/collections/*/documents.jsonl': 'cat',
    "jq .needle /mongodb/shop/collections/*/documents.jsonl": 'jq',
    // Any glob whose last name can be a table's rows.
    'grep -i needle /airtable/bases/Sales__app1/*/*.json*': 'grep',
    'grep needle /mongodb/shop/collections/*/*': 'grep',
    'grep needle /airtable/bases/*/*/records.jsonl': 'grep',
    'tail -n +1 /airtable/bases/Sales__app1/*/records.jsonl': 'tail',
    'head -n 1 /mongodb/shop/collections/*/documents.jsonl': 'head',
  })) {
    const { code, stderr } = await run(line)
    assert.notEqual(code, 0, line)
    assert.match(stderr, new RegExp(`^${name}: Permission denied$`, 'm'), line)
  }
})

test('a bounded walk, a name-only search and anything below a whole mount run', async () => {
  for (const line of [
    "find /data -maxdepth 3 -name '*.csv'",
    'find / -maxdepth 1',
    'tree -L 2 /airtable',
    'grep -rl needle /data',
    'grep -rq needle /data',
    'rg -l needle /mongodb/shop',
    // One repository, one table and /tmp are each meant to be searched.
    'grep -rn needle /data/repos/demo',
    `find ${TABLE}`,
    'grep -rn needle /tmp',
    // Reads that walk nothing, and parts of a table.
    'ls /airtable/bases/Sales__app1',
    `cat ${TABLE}/table.json`,
    `head -1 ${TABLE}/records.jsonl`,
    `grep needle ${TABLE}/records.jsonl`,
    'cat /mongodb/shop/collections/orders/schema.json',
    `head -1 ${DOCUMENTS}`,
    `grep needle ${DOCUMENTS}`,
    `head -1 ${ROWS}`,
    `grep needle ${ROWS}`,
    `jq .needle ${ROWS}`,
    // Every table listed or counted, or searched for names only.
    'wc -l /airtable/bases/Sales__app1/*/records.jsonl',
    'ls -l /mongodb/shop/collections/*/documents.jsonl',
    'head -n 5 /mongodb/shop/collections/*/schema.json',
    'grep -l needle /airtable/bases/Sales__app1/*/records.jsonl',
    'cat /mongodb/shop/collections/*/schema.json',
    'grep needle /airtable/bases/Sales__app1/*/*.json',
    // One table's views, and a glob that names some tables, not every one.
    `grep needle ${TABLE}/views/*.jsonl`,
    'grep needle /airtable/bases/Sales__app1/Orders*/records.jsonl',
  ]) {
    const { code, stderr } = await run(line)
    assert.equal(code, 0, `${line}: ${stderr}`)
  }
})

test('a Notion search or database query that asks for everything is refused', async () => {
  for (const line of [
    'notion post-search',
    "notion post-search '{}'",
    `notion post-search '{"query": " ", "page_size": 100}'`,
    `notion post-search '{"start_cursor": "c1"}'`,
    `notion post-database-query '{"database_id": "d1"}'`,
    `notion post-database-query '{"database_id": "d1", "filter": {}, "filter_properties": []}'`,
    `notion post-database-query '{"database_id": "d1", "sorts": [{"property": "Name", "direction": "ascending"}]}'`,
    // The words the tool is handed, however the line spells them.
    `args='{"database_id": "d1"}'; notion post-database-query "$args"`,
    `echo "$(notion post-search '{}')"`,
  ]) {
    const { stderr } = await run(line)
    assert.match(stderr, /^notion: Permission denied$/m, line)
    assert.doesNotMatch(stderr, NO_SESSION, line)
  }
})

test('a Notion search or query that says what it wants reaches the tool', async () => {
  for (const line of [
    `notion post-search '{"query": "Sales"}'`,
    `notion post-search '{"filter": {"value": "database", "property": "object"}}'`,
    `notion post-database-query '{"database_id": "d1", "filter": {"property": "Name", "rich_text": {"contains": "a"}}}'`,
    `notion post-database-query '{"database_id": "d1", "filter_properties": ["Name"]}'`,
    `notion get-user '{"user_id": "u1"}'`,
    'notion post-search --help',
    // An argument that does not parse is the tool's to refuse.
    "notion post-search '{'",
  ]) {
    const { code, stderr } = await run(line)
    assert.notEqual(code, 0, line)
    assert.match(stderr, NO_SESSION, line)
  }
})
