// CLI transport into the original server handlers; no MCP client is involved.
import http from 'node:http'
import { writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { resolve, relative, isAbsolute } from 'node:path'

export async function loadOriginal(entry) {
  const require = createRequire(pathToFileURL(entry))
  const { Server } = await import(
    pathToFileURL(
      require
        .resolve('@modelcontextprotocol/sdk/server/index.js')
        .replace('/dist/cjs/', '/dist/esm/'),
    )
  )
  const handlers = new Map()
  let ready
  const connected = new Promise((done) => {
    ready = done
  })
  const register = Server.prototype.setRequestHandler
  Server.prototype.setRequestHandler = function (schema, handler) {
    const method = schema.shape.method.value
    if (['tools/list', 'tools/call'].includes(method)) handlers.set(method, handler)
    return register.call(this, schema, handler)
  }
  Server.prototype.connect = async function () {
    ready()
  }
  process.argv = [process.argv[0], entry]
  // This process is `node -e`, and commander reads eval mode off execArgv
  // and then takes argv[1] -- the entry -- for a user argument: 12306-mcp
  // died with "too many arguments". The handlers are loaded here, not run
  // as a script, so the entry sees a plain `node entry` invocation.
  process.execArgv = process.execArgv.filter(
    (flag) => !['-e', '--eval', '-p', '--print'].includes(flag),
  )
  await import(pathToFileURL(entry))
  await connected
  if (!handlers.has('tools/list') || !handlers.has('tools/call')) {
    throw new Error('Original tool handlers were not registered')
  }
  return handlers
}

export async function serveOriginal(entry, endpoint, virtualRoot = '/work') {
  const handlers = await loadOriginal(entry)
  const server = http.createServer(async (request, response) => {
    try {
      let result
      if (request.method === 'GET' && request.url === '/tools') {
        result = await handlers.get('tools/list')({ method: 'tools/list' })
      } else if (request.method === 'POST' && request.url === '/call') {
        const chunks = []
        for await (const chunk of request) chunks.push(chunk)
        result = await handlers.get('tools/call')(
          {
            method: 'tools/call',
            params: cliArguments(JSON.parse(Buffer.concat(chunks).toString()), virtualRoot),
          },
          { signal: new AbortController().signal },
        )
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
    writeFileSync(endpoint, `http://127.0.0.1:${server.address().port}`),
  )
}

export function cliArguments(params, virtualRoot = '/work', workspace = process.cwd()) {
  if (
    ['canvas_upload_file_from_path', 'canvas_submit_assignment_with_file'].includes(params.name)
  ) {
    const file = params.arguments?.file_path
    if (typeof file === 'string') {
      const local = resolve(
        workspace,
        file.startsWith(virtualRoot + '/') ? file.slice(virtualRoot.length + 1) : file,
      )
      const inside = relative(workspace, local)
      if (inside === '..' || inside.startsWith('../') || isAbsolute(inside))
        throw new Error(`Upload a file under ${virtualRoot}`)
      return { ...params, arguments: { ...params.arguments, file_path: local } }
    }
  }
  return params
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await serveOriginal(...process.argv.slice(2))
}
