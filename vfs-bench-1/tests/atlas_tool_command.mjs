import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { test } from 'node:test'
import { toolCommand } from '../cli/mcpatlas/tool.mjs'
import { NOOPAccessor } from '../submodule/mirage/typescript/packages/core/dist/accessor/base.js'

// A tool server that lists one tool and records every call it is sent.
async function server(tool) {
  const calls = []
  const http = createServer((request, response) => {
    let body = ''
    request.on('data', (chunk) => (body += chunk))
    request.on('end', () => {
      response.setHeader('Content-Type', 'application/json')
      if (request.url === '/tools') {
        response.end(JSON.stringify({ tools: [{ name: tool, description: '', inputSchema: {} }] }))
        return
      }
      calls.push(JSON.parse(body))
      response.end(JSON.stringify({ content: [{ type: 'text', text: 'ok' }] }))
    })
  })
  await new Promise((resolve) => http.listen(0, '127.0.0.1', resolve))
  return { calls, apiBase: `http://127.0.0.1:${http.address().port}`, close: () => http.close() }
}

async function run(service, argv, apiBase) {
  const [, result] = await toolCommand(service).handlers[''].fn(
    new NOOPAccessor({ apiBase }),
    [],
    [],
    { argv },
  )
  assert.equal(result.exitCode, 0)
}

test('met-museum get-museum-object is sent with returnImage off, as upstream sends it', async () => {
  const met = await server('get-museum-object')
  try {
    await run('met-museum', ['get-museum-object', '{"objectId":1}'], met.apiBase)
    await run('met-museum', ['get-museum-object', '{"objectId":1,"returnImage":true}'], met.apiBase)
    assert.deepEqual(
      met.calls.map((call) => call.arguments),
      [
        { objectId: 1, returnImage: false },
        { objectId: 1, returnImage: false },
      ],
    )
  } finally {
    met.close()
  }
})

test('other tools are sent their arguments unchanged', async () => {
  const other = await server('get-object')
  try {
    await run('other', ['get-object', '{"objectId":1,"returnImage":true}'], other.apiBase)
    assert.deepEqual(other.calls[0].arguments, { objectId: 1, returnImage: true })
  } finally {
    other.close()
  }
})
