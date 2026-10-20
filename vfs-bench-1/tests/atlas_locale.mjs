import assert from 'node:assert/strict'
import { existsSync, readdirSync } from 'node:fs'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  Workspace,
  configToWorkspaceArgs,
  loadWorkspaceConfig,
  loadWorkspaceConfigFile,
} from '../submodule/mirage/typescript/packages/node/dist/index.js'

const ATLAS = fileURLToPath(new URL('../task/mcpatlas/', import.meta.url))
// Upstream's servers run under LC_CTYPE=C.UTF-8, where `.` is one
// character: this line prints 1 there, and 0 where mirage matches bytes.
const LINE = "printf '\\303\\251x\\n' | grep -c '^.x$'"
// Every `${...}` a task's yaml names, answered with a placeholder: the
// file is only loaded here, and nothing it names is reached.
const ENV = new Proxy({}, { get: (_, key) => (typeof key === 'string' ? 'x' : undefined), has: () => true })

async function count(env) {
  const args = await configToWorkspaceArgs(
    loadWorkspaceConfig({ mode: 'EXEC', mounts: { '/tmp': { vfs: 'ram' } }, ...(env ? { env } : {}) }),
  )
  const workspace = new Workspace({ ...args.mounts }, args.options)
  try {
    const result = await workspace.shell(LINE)
    return new TextDecoder().decode(result.stdout).trim()
  } finally {
    await workspace.close()
  }
}

test('without a UTF-8 locale mirage matches bytes', async () => {
  assert.equal(await count(null), '0')
})

test("every Atlas workspace's env matches whole characters", async () => {
  const configs = readdirSync(ATLAS)
    .map((task) => `${ATLAS}${task}/vfs/workspace.yaml`)
    .filter((path) => existsSync(path))
  assert.equal(configs.length, 100)
  for (const path of configs) {
    assert.equal(await count(loadWorkspaceConfigFile(path, ENV).env), '1', path)
  }
})
