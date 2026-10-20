// Send the Atlas GitHub MCP server to mirage's GitHub fake instead of
// api.github.com.
//
// `@smithery/mcp-github` reaches GitHub only through Octokit, and Octokit
// only through the global `fetch`; the server takes a token and nothing
// else, and Node 20's `fetch` honours no proxy variable. Swapping the global
// before the server's module graph is built moves the origin and nothing
// more: the tools, their schemas and every reply's shape are the server's
// own, as `redirect/fetch/fetch_hook.mjs` leaves the fetch server's.
//
// Loaded with `node --import`, which the Atlas image's servers take through
// NODE_OPTIONS:
//
//     GITHUB_API_URL=http://host:port \
//       node --import ./redirect/github/github_hook.mjs <server>/dist/cli.js

const target = process.env.GITHUB_API_URL
if (!target) throw new Error('GITHUB_API_URL is not set')
const ORIGIN = 'https://api.github.com'
const base = target.replace(/\/$/, '')
const original = globalThis.fetch

function moved(url) {
  const text = String(url)
  return text === ORIGIN || text.startsWith(`${ORIGIN}/`) ? base + text.slice(ORIGIN.length) : text
}

globalThis.fetch = (input, init) => {
  if (input instanceof Request) {
    const url = moved(input.url)
    return original(url === input.url ? input : new Request(url, input), init)
  }
  return original(moved(input instanceof URL ? input.href : input), init)
}
