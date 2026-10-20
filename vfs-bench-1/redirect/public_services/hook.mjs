// Redirect transport URLs only, retaining the pinned server's handlers/schemas.
import { registerHooks } from 'node:module'
const base = process.env.PUBLIC_SERVICE_URL
if (!base) throw new Error('Public service transport is not running')
const roots = new Map([
  ['https://maps.googleapis.com/', `${base}/maps/`],
  ['https://kyfw.12306.cn', `${base}/rail`],
  ['https://search.12306.cn', `${base}/rail-search`],
  ['https://www.12306.cn', `${base}/rail-web`],
])
registerHooks({
  load(url, context, nextLoad) {
    const result = nextLoad(url, context)
    if (
      url.endsWith('/server-google-maps/dist/index.js') ||
      url.endsWith('/12306-mcp/build/index.js')
    ) {
      let source =
        typeof result.source === 'string' ? result.source : Buffer.from(result.source).toString()
      for (const [original, target] of roots) source = source.replaceAll(original, target)
      return { ...result, source }
    }
    if (url.includes('/youtube-mcp/src/dist/services/') && result.format === 'module') {
      let source =
        typeof result.source === 'string' ? result.source : Buffer.from(result.source).toString()
      source = source.replaceAll(
        "version: 'v3',",
        `version: 'v3', rootUrl: ${JSON.stringify(base + '/youtube/')},`,
      )
      source = source.replaceAll(
        'version: "v3",',
        `version: "v3", rootUrl: ${JSON.stringify(base + '/youtube/')},`,
      )
      return { ...result, source }
    }
    return result
  },
})
