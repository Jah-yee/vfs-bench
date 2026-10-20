import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { cliArguments } from '../server/clients/original_tools.mjs'
import { nativeCommand } from '../cli/native.mjs'
import { materialize } from '../submodule/mirage/typescript/packages/core/dist/io/types.js'
import { yieldBytes } from '../submodule/mirage/typescript/packages/core/dist/io/stream.js'
import { NOOPAccessor } from '../submodule/mirage/typescript/packages/core/dist/accessor/base.js'
import { renderToolResult } from '../cli/toolathlon/tool-client.mjs'

test('Canvas maps only file arguments into the task workspace', () => {
  const args = {
    name: 'canvas_upload_file_from_path',
    arguments: {
      file_path: '/workspace/report.txt',
      title: '/workspace is literal content',
    },
  }
  assert.deepEqual(cliArguments(args, '/workspace', '/tmp/task'), {
    ...args,
    arguments: { ...args.arguments, file_path: '/tmp/task/report.txt' },
  })
  assert.equal(args.arguments.file_path, '/workspace/report.txt')
  const message = {
    name: 'canvas_create_announcement',
    arguments: { message: '/workspace/report.txt' },
  }
  assert.deepEqual(cliArguments(message, '/workspace', '/tmp/task'), message)
  assert.throws(() =>
    cliArguments(
      { ...args, arguments: { file_path: '/workspace/../secret' } },
      '/workspace',
      '/tmp/task',
    ),
  )
})

test('Native kubectl preserves stdin and maps separated and equals file options', async () => {
  const argv = [
    'apply',
    '-f',
    '/workspace/report.yaml',
    '--filename=/workspace/other.yaml',
    '/workspace-other',
  ]
  const command = nativeCommand('kubectl', '')
  const [stream, result] = await command.handlers[''].fn(
    new NOOPAccessor({
      virtualRoot: '/workspace',
      workdir: '/tmp',
      env: { PATH: process.env.PATH },
      launch: [
        process.execPath,
        '-e',
        'const chunks=[];process.stdin.on("data",c=>chunks.push(c));process.stdin.on("end",()=>console.log(JSON.stringify({args:process.argv.slice(1),stdin:Buffer.concat(chunks).toString()})))',
        '--',
      ],
    }),
    [],
    [],
    { argv, stdin: yieldBytes(new TextEncoder().encode('kind: ConfigMap\n')) },
  )
  assert.equal(result.exitCode, 0)
  const actual = JSON.parse(new TextDecoder().decode(await materialize(stream)))
  assert.equal(actual.stdin, 'kind: ConfigMap\n')
  assert.deepEqual(actual.args, [
    'apply',
    '-f',
    '/tmp/report.yaml',
    '--filename=/tmp/other.yaml',
    '/workspace-other',
  ])
})

test("Native commands run where the shell has cd'd", async (t) => {
  const work = realpathSync(mkdtempSync(join(tmpdir(), 'native-cwd-')))
  t.after(() => rmSync(work, { recursive: true, force: true }))
  mkdirSync(join(work, 'repo'))
  const run = async (config, pwd, argv = []) => {
    const [stream, result] = await nativeCommand('kubectl', '').handlers[''].fn(
      new NOOPAccessor({ virtualRoot: '/workspace', env: { PATH: process.env.PATH }, ...config }),
      [],
      [],
      { argv, stdin: null, env: pwd === undefined ? {} : { PWD: pwd } },
    )
    assert.equal(result.exitCode, 0)
    return new TextDecoder().decode(await materialize(stream)).trim()
  }
  const local = {
    workdir: work,
    launch: [process.execPath, '-e', 'console.log(require("fs").realpathSync(process.cwd()))'],
  }
  assert.equal(await run(local, '/workspace/repo'), join(work, 'repo'))
  assert.equal(await run(local, '/workspace'), work)
  assert.equal(await run(local, '/tmp'), work)
  assert.equal(await run(local, undefined), work)
  assert.equal(await run(local, '/workspace/gone'), work)
  writeFileSync(join(work, 'file'), '')
  assert.equal(await run(local, '/workspace/file'), work)
  assert.equal(await run(local, '/workspace/file/below'), work)
  // Linux's wrappers change directory themselves, after spawn's.
  for (const flag of ['--cwd', '--chdir']) {
    const wrapper = {
      workdir: work,
      launch: [
        process.execPath,
        '-e',
        `process.chdir(process.argv[process.argv.indexOf('${flag}') + 1]);` +
          'console.log(require("fs").realpathSync(process.cwd()))',
        '--',
        flag,
        work,
        '--',
      ],
    }
    assert.equal(await run(wrapper, '/workspace/repo'), join(work, 'repo'))
    assert.equal(await run(wrapper, '/tmp'), work)
  }
  // Over SSH the command line carries the directory, in the sandbox's view.
  const remote = {
    workdir: '/work',
    localWorkdir: work,
    sshCommand: 'exec env kubectl',
    launch: [process.execPath, '-e', 'console.log(process.argv.at(-1))', '--'],
  }
  assert.equal(
    await run(remote, '/workspace/repo', ['apply', '-f', 'preview.yaml']),
    "cd '/work/repo' 2>/dev/null || cd '/work' && exec env kubectl 'apply' '-f' 'preview.yaml'",
  )
  assert.equal(
    await run(remote, '/tmp', ['get', 'pods']),
    "cd '/work' 2>/dev/null || cd '/work' && exec env kubectl 'get' 'pods'",
  )
  // The line itself: into the directory when it exists, else the root.
  const sh = (dir) =>
    spawnSync('/bin/sh', ['-c', `cd '${dir}' 2>/dev/null || cd '${work}' && pwd -P`])
      .stdout.toString()
      .trim()
  assert.equal(sh(join(work, 'repo')), join(work, 'repo'))
  assert.equal(sh(join(work, 'missing')), work)
})

test('CLI result rendering preserves text bytes and non-text envelopes', () => {
  assert.equal(
    renderToolResult({
      content: [
        { type: 'text', text: 'first\n' },
        { type: 'text', text: 'second' },
      ],
    }),
    'first\n\nsecond',
  )
  const result = {
    content: [{ type: 'image', mimeType: 'image/png', data: 'AA==' }],
    isError: false,
  }
  assert.deepEqual(JSON.parse(renderToolResult(result)), result)
})
