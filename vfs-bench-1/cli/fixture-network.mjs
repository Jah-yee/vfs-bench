// Mirage's builtin HTTP commands (curl, wget, git's transport) all fetch
// from one function in core's http module, which no longer takes a proxy
// base (upstream dropped `setHttpProxyBase` in 93b7e6d1f1). The same rewrite
// it applied is applied here instead, to that function's fetches only, so a
// service client in the same process keeps its own network. Keep loopback
// fixtures reachable, but never follow a public URL or redirect from them.
import http from 'node:http'
import { realpathSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { registerInsecureFetch } from '../submodule/mirage/typescript/packages/core/dist/commands/builtin/utils/http.js'
// The node package registers curl -k's fetch when it loads; it is loaded
// first so the registration below is the one that stays.
import '../submodule/mirage/typescript/packages/node/dist/commands/builtin/utils/http.js'

const local = (url) =>
  ['http:', 'https:'].includes(url.protocol) &&
  ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
const proxy = http.createServer(async (request, response) => {
  try {
    const target = new URL(new URL(request.url, 'http://localhost').searchParams.get('url'))
    if (!local(target)) throw new Error('Public network is outside the fixture')
    const parts = []
    for await (const part of request) parts.push(part)
    const headers = { ...request.headers }
    delete headers.host
    delete headers.connection
    delete headers['content-length']
    const body = ['GET', 'HEAD'].includes(request.method) ? undefined : Buffer.concat(parts)
    const controller = new globalThis.AbortController()
    response.on('close', () => controller.abort())
    const reply = await fetch(target, {
      method: request.method,
      headers,
      body,
      redirect: 'manual',
      signal: controller.signal,
    })
    // The rewrite applies to every redirect hop. Preserve Location
    // and let the builtin keep its own redirect and timeout semantics.
    const outgoing = Object.fromEntries(reply.headers)
    // Fetch decodes compression, so remove the original wire lengths.
    delete outgoing['content-encoding']
    delete outgoing['content-length']
    delete outgoing['transfer-encoding']
    response.writeHead(reply.status, outgoing)
    response.end(Buffer.from(await reply.arrayBuffer()))
  } catch {
    request.socket.destroy()
  }
})
await new Promise((resolve) => proxy.listen(0, '127.0.0.1', resolve))
proxy.unref()
const base = `http://127.0.0.1:${proxy.address().port}/`

// Upstream's `applyProxy`, as it was before 93b7e6d1f1.
const applyProxy = (url) => {
  if (url.startsWith(base) || url.startsWith('/')) return url
  const sep = base.includes('?') ? '&' : '?'
  return `${base}${sep}url=${encodeURIComponent(url)}`
}

// A fetch is the builtin's when core's http module is the frame calling it.
const HTTP_MODULE = pathToFileURL(
  realpathSync(
    fileURLToPath(
      new URL(
        '../submodule/mirage/typescript/packages/core/dist/commands/builtin/utils/http.js',
        import.meta.url,
      ),
    ),
  ),
).href
const direct = globalThis.fetch
globalThis.fetch = (input, init) =>
  direct(
    typeof input === 'string' && new Error().stack.includes(`${HTTP_MODULE}:`)
      ? applyProxy(input)
      : input,
    init,
  )
// curl -k went through the same rewrite, so it reaches the proxy over
// plain HTTP like every other builtin fetch.
registerInsecureFetch((input, init) => globalThis.fetch(input, init))
