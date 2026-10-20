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

const POLICY = fileURLToPath(new URL('../task/toolathlon/task_paths.py', import.meta.url))
const PROGRAM = [{ script: POLICY, runtime: 'monty' }]

// Disk trees stand in for a task's mounts: the policy reads a command's
// name, its words and the paths it resolves to, never what serves them.
// Two branch mounts under /repo, as sync-todo-to-readme has, so /repo
// holds nothing but mounts.
const FILES = {
  'workspace/notes.txt': 'needle\n',
  'gd/sheet.gsheet.json': '{"needle": 1}\n',
  'main/README.md': 'needle\n',
  'dev/README.md': 'needle\n',
}

let root
let workspace

before(async () => {
  root = mkdtempSync(join(tmpdir(), 'task-paths-'))
  for (const [path, text] of Object.entries(FILES)) {
    mkdirSync(dirname(join(root, path)), { recursive: true })
    writeFileSync(join(root, path), text)
  }
  const disk = (dir) => ({ vfs: 'disk', config: { root: join(root, dir) } })
  // The policy as `workspace_config` in task/toolathlon/__init__.py loads it.
  const args = await configToWorkspaceArgs(
    loadWorkspaceConfig({
      mode: 'EXEC',
      runtimes: ['workspace'],
      mounts: {
        '/tmp': { vfs: 'ram' },
        '/workspace': disk('workspace'),
        '/gd': disk('gd'),
        '/repo/main': disk('main'),
        '/repo/dev': disk('dev'),
      },
      profiles: {
        default: { cwd: '/workspace', policy: { pre_execute: PROGRAM, pre_command: PROGRAM } },
      },
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

test('a walk of / and a read outside the task mounts are refused', async () => {
  const refused = {
    'find /': 'find',
    "find / -name '*.py'": 'find',
    'find / -maxdepth 1': 'find',
    'grep -rn needle /': 'grep',
    'ls -R /': 'ls',
    'du -a /': 'du',
    // Mirage's own mounts: the session's history, the CLI wrappers, the
    // device files.
    'cat /.bash_history': 'cat',
    'ls /usr/bin': 'ls',
    'cat /usr/bin/ls': 'cat',
    'cat $(which ls)': 'cat',
    'ls /dev': 'ls',
    // Paths no mount serves.
    'ls /etc': 'ls',
    'cat /proc/net/tcp': 'cat',
    'ls -la /root /home': 'ls',
    'grep -rn needle /usr': 'grep',
    // `..` out of a mount, after an unset variable or a glob that matched
    // nothing too: Mirage resolves the path before the policy sees it.
    'cat /workspace/../.bash_history': 'cat',
    'cat /workspace/$unset/../../.bash_history': 'cat',
    'cat /workspace/*missing*/../../.bash_history': 'cat',
    'ls /workspace/../usr/bin': 'ls',
    'find /workspace/.. -name notes.txt': 'find',
  }
  for (const [line, name] of Object.entries(refused)) {
    const { code, stderr } = await run(line)
    assert.equal(code, 126, line)
    assert.match(stderr, new RegExp(`^${name}: Permission denied$`, 'm'), line)
  }
})

test('a walk from / is refused after a cd to it', async () => {
  assert.equal((await run('cd /')).code, 0)
  const { code, stderr } = await run('find . -name notes.txt')
  assert.equal(code, 126)
  assert.match(stderr, /^find: Permission denied$/m)
  assert.equal((await run('cd /workspace')).code, 0)
})

test('a read or search inside the task mounts runs', async () => {
  for (const line of [
    // `/` and /repo hold the mounts, and listing one is how a mount is found.
    'ls /',
    'ls /repo',
    'ls -la /workspace /gd',
    'find /workspace -name notes.txt',
    'grep -rn needle /gd',
    'grep -rn needle /tmp',
    'find /repo -name README.md',
    'grep -rn needle /repo/',
    'for branch in main dev; do cat /repo/$branch/README.md; done',
    'cat /workspace/*.txt',
    // A glob that matches nothing reaches the policy as typed, and answers
    // as a missing file does rather than as a refusal.
    'ls /repo/*/missing 2>/dev/null || echo none',
    'grep needle notes.txt 2>/dev/null',
    'cat /gd/sheet.gsheet.json > /dev/null',
    // Commands that do not read files are not judged.
    'which ls',
    'echo /etc/hosts',
  ]) {
    const { code, stderr } = await run(line)
    assert.equal(code, 0, `${line}: ${stderr}`)
  }
})
