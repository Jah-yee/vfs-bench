// The CLI transport invokes the original backend, including its Zod parser
// and response serializer. Browser behavior does not live in this adapter.
import http from 'node:http'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { BrowserServerBackend } from '../../vendor/browser-mcp/node_modules/@lockon0927/playwright-mcp-with-chunk/lib/browserServerBackend.js'
import { contextFactory } from '../../vendor/browser-mcp/node_modules/@lockon0927/playwright-mcp-with-chunk/lib/browserContextFactory.js'
import { resolveCLIConfig } from '../../vendor/browser-mcp/node_modules/@lockon0927/playwright-mcp-with-chunk/lib/config.js'
import { Context } from '../../vendor/browser-mcp/node_modules/@lockon0927/playwright-mcp-with-chunk/lib/context.js'
import { zodToJsonSchema } from '../../vendor/browser-mcp/node_modules/zod-to-json-schema/dist/esm/index.js'

const [settings, endpointFile, listenHost = '127.0.0.1', listenPort = '0', virtualRoot = '/work'] =
  process.argv.slice(2)
const config = await resolveCLIConfig(JSON.parse(await fs.readFile(settings, 'utf8')))
const backend = new BrowserServerBackend(config, contextFactory(config.browser))
await backend.initialize()
const tools = backend.tools()
const workspace = process.cwd()
const nativePath = (value) =>
  value === virtualRoot || value.startsWith(virtualRoot + '/')
    ? workspace + value.slice(virtualRoot.length)
    : value
const visibleText = (value) =>
  workspace === virtualRoot
    ? value
    : value.split(workspace).join(virtualRoot).split(encodeURI(workspace)).join(virtualRoot)
function nativeArguments(name, args) {
  if (name === 'browser_file_upload' && args.paths)
    return { ...args, paths: args.paths.map(nativePath) }
  if (name === 'browser_navigate' && args.url.startsWith('file:')) {
    const url = new URL(args.url)
    const file = fileURLToPath(url)
    if (nativePath(file) !== file) {
      url.pathname = pathToFileURL(path.resolve(nativePath(file))).pathname
      return { ...args, url: url.href }
    }
  }
  return args
}
const errorResult = (error) => ({ content: [{ type: 'text', text: String(error) }], isError: true })
const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', 'application/json')
  try {
    if (req.method === 'GET' && req.url === '/tools') {
      res.end(
        JSON.stringify({
          tools: tools.map((tool) => ({
            name: tool.name,
            description: tool.description,
            inputSchema: zodToJsonSchema(tool.inputSchema),
            annotations: {
              title: tool.title,
              readOnlyHint: tool.type === 'readOnly',
              destructiveHint: tool.type === 'destructive',
              openWorldHint: true,
            },
          })),
        }),
      )
      return
    }
    if (req.method !== 'POST' || req.url !== '/call') {
      res.writeHead(404).end(JSON.stringify(errorResult('Unknown browser endpoint')))
      return
    }
    const chunks = []
    for await (const chunk of req) chunks.push(chunk)
    const request = JSON.parse(Buffer.concat(chunks).toString())
    const tool = tools.find((candidate) => candidate.name === request.name)
    if (!tool) {
      res.end(JSON.stringify(errorResult(`Tool "${request.name}" not found`)))
      return
    }
    const args = tool.inputSchema.parse(request.arguments || {})
    const result = await backend.callTool(tool, nativeArguments(tool.name, args))
    result.content = result.content.map((block) =>
      block.type === 'text' ? { ...block, text: visibleText(block.text) } : block,
    )
    res.end(JSON.stringify(result))
  } catch (error) {
    res.end(JSON.stringify(errorResult(visibleText(String(error)))))
  }
})
await new Promise((resolve) => server.listen(Number(listenPort), listenHost, resolve))
await fs.writeFile(endpointFile, `http://127.0.0.1:${server.address().port}`, { mode: 0o600 })
for (const signal of ['SIGTERM', 'SIGINT']) {
  process.on(signal, async () => {
    server.closeAllConnections()
    server.close()
    await Context.disposeAll()
    process.exit(0)
  })
}
