// Answer the fetch MCP server from a capture instead of the network.
//
// `@tokenizin/mcp-npx-fetch` reaches the internet through one call to the
// global `fetch` in `Fetcher._fetch`, and everything else it does -- the
// four tools, their schemas, the JSDOM and Turndown transforms, the shape
// of an error reply -- happens after that call returns. Replacing the
// global therefore leaves upstream's surface exactly as published and
// changes only where the bytes come from, which is the same arrangement
// `pg_adapter.py` gives the yahoo-finance server.
//
// Loaded with `node --import`, so it runs before the server's own module
// graph and the global is already swapped by the time Fetcher is imported.
//
//     WEB_FIXTURE=task/toolathlon/course-schedule/shared/web_fixture.json \
//       node --import ./redirect/fetch/fetch_hook.mjs <server>/dist/index.js
//
// The capture is written by task/toolathlon/script/capture_web.py, and the
// mirage arm's `fetch` CLI runs these same hooked handlers over it.

import { readFileSync } from 'node:fs'

const path = process.env.WEB_FIXTURE
if (!path) throw new Error('WEB_FIXTURE is not set')
const captured = JSON.parse(readFileSync(path, 'utf-8'))

// Trailing slashes only: a captured URL and the one an agent types differ
// there often enough to be worth absorbing, and anywhere else a difference
// is a different request and should miss.
function key(url) {
  const text = String(url)
  return text.endsWith('/') ? text.slice(0, -1) : text
}

globalThis.fetch = async (url) => {
  const entry = captured[key(url)]
  if (entry === undefined) {
    // Upstream wraps this as `Failed to fetch <url>: <message>`, which is
    // what the agent sees. Saying what actually happened beats imitating a
    // DNS failure and sending it into retries.
    throw new Error('no capture for this URL in the offline web fixture')
  }
  return new Response(entry.body, {
    status: entry.status,
    headers: { 'Content-Type': entry.content_type },
  })
}
