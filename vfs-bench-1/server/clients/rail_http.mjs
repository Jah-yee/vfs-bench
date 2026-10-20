// Keep 12306's original Node/axios HTTP transport behind the shared cache.
// Its edge returns error HTML for the equivalent Python requests client.
import http from 'node:http'
import { createRequire } from 'node:module'

const require = createRequire(new URL('../../vendor/rail-mcp/package.json', import.meta.url))
const axios = require('axios')
const origins = new Set([
  'https://kyfw.12306.cn',
  'https://search.12306.cn',
  'https://www.12306.cn',
])
const server = http.createServer(async (request, response) => {
  try {
    if (request.method !== 'POST' || request.url !== '/') {
      response.writeHead(404).end()
      return
    }
    const chunks = []
    for await (const chunk of request) chunks.push(chunk)
    const { url, headers } = JSON.parse(Buffer.concat(chunks).toString())
    if (!origins.has(new URL(url).origin)) throw new Error('Expected a 12306 URL')
    const result = await axios.get(url, {
      headers,
      responseType: 'arraybuffer',
      timeout: 90000,
      validateStatus: () => true,
    })
    const replyHeaders = Object.fromEntries(
      Object.entries(result.headers).filter(
        ([key]) =>
          ![
            'content-encoding',
            'transfer-encoding',
            'content-length',
            'connection',
            'set-cookie',
          ].includes(key),
      ),
    )
    response.setHeader('Content-Type', 'application/json')
    response.end(
      JSON.stringify({
        status: result.status,
        headers: replyHeaders,
        cookies: result.headers['set-cookie'] || [],
        body: Buffer.from(result.data).toString('base64'),
      }),
    )
  } catch {
    response.writeHead(502).end('Railway HTTP request failed')
  }
})
server.listen(0, '127.0.0.1', () => {
  console.log(`http://127.0.0.1:${server.address().port}`)
})
