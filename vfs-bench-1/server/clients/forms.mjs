// The CLI calls the original server's handlers directly, without stdio.
import http from 'node:http'
import '../../redirect/forms/google_hook.mjs'
import { Server } from '../../vendor/forms-mcp/src/node_modules/@modelcontextprotocol/sdk/dist/esm/server/index.js'

const handlers = new Map()
const register = Server.prototype.setRequestHandler
Server.prototype.setRequestHandler = function (schema, handler) {
  const method = schema.shape.method.value
  if (['tools/list', 'tools/call'].includes(method)) handlers.set(method, handler)
  return register.call(this, schema, handler)
}
Server.prototype.connect = async function () {}
await import('../../vendor/forms-mcp/src/build/index.js')

const server = http.createServer(async (request, response) => {
  try {
    let result
    if (request.method === 'GET' && request.url === '/tools') {
      result = await handlers.get('tools/list')({ method: 'tools/list' })
    } else if (request.method === 'POST' && request.url === '/call') {
      const chunks = []
      for await (const chunk of request) chunks.push(chunk)
      result = await handlers.get('tools/call')({
        method: 'tools/call',
        params: JSON.parse(Buffer.concat(chunks).toString()),
      })
    } else {
      response.writeHead(404).end()
      return
    }
    response.setHeader('Content-Type', 'application/json')
    response.end(JSON.stringify(result))
  } catch (error) {
    response
      .writeHead(500, { 'Content-Type': 'application/json' })
      .end(JSON.stringify({ error: error.message }))
  }
})
server.listen(0, '127.0.0.1', () =>
  process.stdout.write(JSON.stringify({ port: server.address().port }) + '\n'),
)
