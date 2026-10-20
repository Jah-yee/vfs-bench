import assert from 'node:assert/strict'
import http from 'node:http'
import { test } from 'node:test'
import { httpRequest } from '../submodule/mirage/typescript/packages/core/dist/commands/builtin/utils/http.js'
import { runBrowser } from '../cli/toolathlon/browser-client.mjs'

test('builtin HTTP permits fixtures and blocks public URLs and redirects', async (t) => {
  // An escaped public request would succeed, so DNS failure cannot make
  // this boundary test pass accidentally. No external network is used.
  const originalFetch = globalThis.fetch
  t.mock.method(globalThis, 'fetch', (url, ...args) =>
    new URL(url).hostname === 'example.invalid'
      ? Promise.resolve(new Response('public bytes'))
      : originalFetch(url, ...args),
  )
  // The hook wraps the fetch it finds, so it goes on over the escape.
  await import('../cli/fixture-network.mjs')
  const server = http.createServer((request, response) => {
    if (request.url === '/redirect') {
      response.writeHead(302, { location: 'https://example.invalid/outside' })
    } else if (request.url === '/local-redirect') {
      response.writeHead(302, { location: '/fixture' })
    } else response.write('fixture bytes')
    response.end()
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  try {
    assert.equal(
      new TextDecoder().decode((await httpRequest(base + '/fixture')).body),
      'fixture bytes',
    )
    assert.equal(
      new TextDecoder().decode((await httpRequest(base + '/local-redirect')).body),
      'fixture bytes',
    )
    await assert.rejects(httpRequest('https://example.invalid/outside'))
    await assert.rejects(httpRequest(base + '/redirect'))
    const redirect = await httpRequest(base + '/redirect', { followRedirects: false })
    assert.equal(redirect.status, 302)
    assert.equal(Object.fromEntries(redirect.headers).location, 'https://example.invalid/outside')
  } finally {
    server.closeAllConnections()
    await new Promise((resolve) => server.close(resolve))
  }
})

test('browser CLI aborts a service call at its configured upstream timeout', async () => {
  const server = http.createServer(() => {})
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  try {
    const result = await runBrowser(
      ['navigate', '{}'],
      `http://127.0.0.1:${server.address().port}`,
      20,
    )
    assert.equal(result.exitCode, 1)
    assert.match(result.stderr, /timeout|aborted/i)
  } finally {
    server.closeAllConnections()
    await new Promise((resolve) => server.close(resolve))
  }
})

// Calendar and Sheets use the same tool client; cancellation must propagate
// through both schema discovery and execution, not just browser commands.
test('Google CLI client aborts discovery and calls at the upstream deadline', async () => {
  const { runTool } = await import('../cli/toolathlon/tool-client.mjs')
  const server = http.createServer(() => {})
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  try {
    for (const argv of [['--help'], ['get_sheet_data', '{}']]) {
      const result = await runTool('sheets', argv, `http://127.0.0.1:${server.address().port}`, 20)
      assert.equal(result.exitCode, 1)
      assert.match(result.stderr, /timeout|aborted/i)
    }
  } finally {
    server.closeAllConnections()
    await new Promise((resolve) => server.close(resolve))
  }
})

// A command is its tool's name with hyphens, less the CLI's prefix; either
// spelling calls the original tool, and one no tool answers to reaches the
// server as typed. Arguments are one JSON object, as upstream's tools take
// them; `-` is not a way to pass them.
test('Toolathlon tool CLIs spell commands with hyphens and call the original tools', async () => {
  const { runTool } = await import('../cli/toolathlon/tool-client.mjs')
  const called = []
  const server = http.createServer((request, response) => {
    let body = ''
    request.on('data', (chunk) => (body += chunk))
    request.on('end', () => {
      if (request.url === '/tools') {
        const tools = ['woo_products_list', 'browser_tab_list', 'browser_navigate_back']
        response.end(JSON.stringify({ tools: tools.map((name) => ({ name, description: name })) }))
        return
      }
      called.push(JSON.parse(body).name)
      response.end(JSON.stringify({ content: [{ type: 'text', text: 'ok' }] }))
    })
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  try {
    const listing = await runTool('woocommerce', ['--help'], base, 1000, 'woo_')
    assert.match(listing.stdout, /^products-list: woo_products_list$/m)
    const help = await runTool('woocommerce', ['products-list', '--help'], base, 1000, 'woo_')
    assert.equal(JSON.parse(help.stdout).name, 'products-list')
    for (const command of ['products-list', 'products_list', 'orders-list']) {
      await runTool('woocommerce', [command, '{}'], base, 1000, 'woo_')
    }
    assert.match((await runBrowser(['--help'], base, 1000)).stdout, /^tab-list: /m)
    for (const command of ['navigate-back', 'navigate_back', 'tab-close']) {
      await runBrowser([command, '{}'], base, 1000)
    }
    const piped = await runTool('woocommerce', ['products-list', '-'], base, 1000, 'woo_')
    assert.equal(piped.exitCode, 1)
    assert.deepEqual(called, [
      'woo_products_list',
      'woo_products_list',
      'woo_orders-list',
      'browser_navigate_back',
      'browser_navigate_back',
      'browser_tab-close',
    ])
  } finally {
    server.closeAllConnections()
    await new Promise((resolve) => server.close(resolve))
  }
})

// A failed call's text is the command's error, so a redirect or pipe of the
// output does not swallow it. A string typed over several lines carries raw
// line breaks, and reaches the tool as the string typed.
test('Toolathlon tool CLIs print a failed call on stderr and take multi-line strings', async () => {
  const { runTool } = await import('../cli/toolathlon/tool-client.mjs')
  const received = []
  const server = http.createServer((request, response) => {
    let body = ''
    request.on('data', (chunk) => (body += chunk))
    request.on('end', () => {
      if (request.url === '/tools') {
        const tools = ['canvas_get_quiz', 'browser_evaluate']
        response.end(JSON.stringify({ tools: tools.map((name) => ({ name, description: name })) }))
        return
      }
      const parameters = JSON.parse(body).arguments
      received.push(parameters)
      response.end(
        JSON.stringify(
          parameters.fail
            ? { content: [{ type: 'text', text: 'Error: Canvas API Error (401)' }], isError: true }
            : { content: [{ type: 'text', text: 'ok' }] },
        ),
      )
    })
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  try {
    const failed = { stdout: '', stderr: 'Error: Canvas API Error (401)', exitCode: 1 }
    assert.deepEqual(
      await runTool('canvas', ['get-quiz', '{"fail": true}'], base, 1000, 'canvas_'),
      failed,
    )
    assert.deepEqual(await runBrowser(['evaluate', '{"fail": true}'], base, 1000), failed)
    const typed = '{"function": "() => {\n\treturn \\"a\\nb\\"\n}"}'
    const ok = { stdout: 'ok', stderr: '', exitCode: 0 }
    assert.deepEqual(await runTool('canvas', ['get-quiz', typed], base, 1000, 'canvas_'), ok)
    assert.deepEqual(await runBrowser(['evaluate', typed], base, 1000), ok)
    assert.deepEqual(received.slice(2), [
      { function: '() => {\n\treturn "a\nb"\n}' },
      { function: '() => {\n\treturn "a\nb"\n}' },
    ])
    // A backslash before a raw line break is still no JSON escape.
    const escaped = await runTool('canvas', ['get-quiz', '{"a": "x\\\ny"}'], base, 1000, 'canvas_')
    assert.equal(escaped.exitCode, 1)
    assert.equal(received.length, 4)
  } finally {
    server.closeAllConnections()
    await new Promise((resolve) => server.close(resolve))
  }
})

// Hub reaches its server through the MCP SDK rather than the tool client,
// so its failed call is checked on its own path, through the shell the
// model types into.
test('Hub CLI prints a failed call on stderr through the workspace shell', async () => {
  const sdk = '../vendor/fetch-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm'
  const { Server } = await import(`${sdk}/server/index.js`)
  const { StreamableHTTPServerTransport } = await import(`${sdk}/server/streamableHttp.js`)
  const { CallToolRequestSchema, ListToolsRequestSchema } = await import(`${sdk}/types.js`)
  const { HUB } = await import('../cli/toolathlon/hub.mjs')
  const { Workspace } =
    await import('../submodule/mirage/typescript/packages/node/dist/workspace.js')
  const { RAMVFS } =
    await import('../submodule/mirage/typescript/packages/core/dist/vfs/ram/ram.js')
  const server = http.createServer(async (request, response) => {
    const mcp = new Server({ name: 'hub', version: '1.0.0' }, { capabilities: { tools: {} } })
    mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        { name: 'repo_details', description: 'repo_details', inputSchema: { type: 'object' } },
      ],
    }))
    mcp.setRequestHandler(CallToolRequestSchema, async (call) =>
      call.params.arguments.fail
        ? { content: [{ type: 'text', text: 'Error: repository not found' }], isError: true }
        : { content: [{ type: 'text', text: 'ok' }] },
    )
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined })
    response.on('close', () => mcp.close())
    await mcp.connect(transport)
    await transport.handleRequest(request, response)
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const endpoint = `http://127.0.0.1:${server.address().port}/mcp`
  const ws = new Workspace(
    { '/work': new RAMVFS() },
    { mode: 'exec', clis: { huggingface: [HUB, { endpoint, timeoutMs: 5000 }] } },
  )
  const shown = async (command) => {
    const result = await ws.shell(command)
    const text = (bytes) => new TextDecoder().decode(bytes)
    return { stdout: text(result.stdout), stderr: text(result.stderr), exitCode: result.exitCode }
  }
  try {
    assert.deepEqual(await shown(`huggingface repo-details '{"fail": true}'`), {
      stdout: '',
      stderr: 'Error: repository not found',
      exitCode: 1,
    })
    // A pipe no longer swallows it.
    assert.deepEqual(await shown(`huggingface repo-details '{"fail": true}' | grep -c .`), {
      stdout: '0\n',
      stderr: 'Error: repository not found',
      exitCode: 1,
    })
    assert.deepEqual(await shown(`huggingface repo-details '{}'`), {
      stdout: 'ok',
      stderr: '',
      exitCode: 0,
    })
  } finally {
    await ws.close()
    server.closeAllConnections()
    await new Promise((resolve) => server.close(resolve))
  }
})

test('native Helm honors its configured terminal deadline', async () => {
  const { nativeCommand } = await import('../cli/native.mjs')
  const { NOOPAccessor } =
    await import('../submodule/mirage/typescript/packages/core/dist/accessor/base.js')
  const cli = nativeCommand('helm', 'test deadline')
  const [, result] = await cli.handlers[''].fn(
    new NOOPAccessor({
      launch: [process.execPath],
      workdir: process.cwd(),
      env: process.env,
      timeoutMs: 30,
    }),
    [],
    [],
    { argv: ['-e', 'setTimeout(() => process.exit(0), 10000)'], stdin: null },
  )
  assert.notEqual(result.exitCode, 0)
})

test('Pyodide workspace executes a file main guard and preserves its exit status', async () => {
  const { Workspace } =
    await import('../submodule/mirage/typescript/packages/node/dist/workspace.js')
  const { RAMVFS } =
    await import('../submodule/mirage/typescript/packages/core/dist/vfs/ram/ram.js')
  const ws = new Workspace(
    { '/work': new RAMVFS() },
    { mode: 'exec', runtimes: ['pyodide', 'workspace'] },
  )
  try {
    await ws.dispatch('write', '/work/submission.py', [
      new TextEncoder().encode(
        "if __name__ == '__main__':\n    print('graded result')\n    raise SystemExit(7)\n",
      ),
    ])
    const result = await ws.shell('python3 /work/submission.py')
    assert.equal(new TextDecoder().decode(result.stdout), 'graded result\n')
    assert.equal(new TextDecoder().decode(result.stderr), '')
    assert.equal(result.exitCode, 7)
  } finally {
    await ws.close()
  }
})
