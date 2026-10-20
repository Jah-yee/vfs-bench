import assert from 'node:assert/strict'
import http from 'node:http'
import { Workspace } from '../submodule/mirage/typescript/packages/node/dist/workspace.js'
import { GSHEET } from '../cli/shims.mjs'
import { CanvasVFS } from '../vfs/canvas.mjs'
import { WooCommerceVFS } from '../vfs/woocommerce.mjs'
import { ServiceClient } from '../server/clients/service_api.mjs'

assert.equal(GSHEET.handlers[''].write, true)

// These small transport fixtures are test data, never benchmark inputs.
for (const kind of ['canvas', 'woocommerce']) {
  const name = kind === 'canvas' ? 'canvas' : 'woo'
  const collection = kind === 'canvas' ? 'courses' : 'products'
  const objects = [
    { id: 1, name: 'First', type: 'simple' },
    { id: 2, name: 'Second', type: 'simple' },
  ]
  let sawFilter = false
  // Requests whose connection the server drops without answering, as the
  // e2b tunnel does under a burst of reads, requests it answers 503, and
  // every attempt by method.
  let drops = 0
  let gateways = 0
  const attempts = { GET: 0, PUT: 0 }
  const auth =
    kind === 'canvas' ? 'Bearer token' : `Basic ${Buffer.from('key:secret').toString('base64')}`
  const server = http.createServer(async (request, response) => {
    assert.equal(request.headers.authorization, auth)
    const url = new URL(request.url, 'http://localhost')
    attempts[request.method] = (attempts[request.method] ?? 0) + 1
    if (drops > 0) {
      drops--
      request.socket.destroy()
      return
    }
    response.setHeader('Content-Type', 'application/json')
    if (gateways > 0) {
      gateways--
      response.writeHead(503)
      response.end(JSON.stringify({ error: 'unavailable' }))
      return
    }
    const path = url.pathname.slice(1)
    let data
    if (path === collection) {
      sawFilter ||= url.searchParams.get('search') === 'term'
      const page = Number(url.searchParams.get('page') || '1')
      if (kind === 'canvas' && page === 1)
        response.setHeader('Link', '<http://localhost/?page=2>; rel="next"')
      if (kind === 'woocommerce') response.setHeader('X-WP-TotalPages', '2')
      data = objects.slice(page - 1, page)
    } else if (path === `${collection}/1` || path === `${collection}/2`) {
      const selected = objects[Number(path.split('/')[1]) - 1]
      if (request.method === 'PUT') {
        const chunks = []
        for await (const chunk of request) chunks.push(chunk)
        Object.assign(selected, JSON.parse(Buffer.concat(chunks)))
      }
      data = selected
    } else {
      response.writeHead(404)
      data = { error: 'missing' }
    }
    response.end(JSON.stringify(data))
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const config = {
    kind,
    apiBase: `http://127.0.0.1:${server.address().port}`,
    token: 'token',
    key: 'key',
    secret: 'secret',
  }
  try {
    const client = new ServiceClient(config)
    assert.deepEqual(
      (await client.list(collection, { search: 'term' })).map((r) => r.id),
      [1, 2],
    )
    assert.ok(sawFilter)
    for (const mount of [`/${name}`, `/nested/${name}`]) {
      const vfs = kind === 'canvas' ? new CanvasVFS(config) : new WooCommerceVFS(config)
      const ws = new Workspace({ [mount]: vfs })
      async function run(command) {
        const result = await ws.shell(command)
        assert.equal(result.exitCode, 0, new TextDecoder().decode(result.stderr))
        return new TextDecoder().decode(result.stdout)
      }
      try {
        const path = `${mount}/${collection}/1.json`
        assert.ok((await run(`ls ${mount}/${collection}`)).includes('2.json'))
        assert.equal(JSON.parse(await run(`cat ${path}`)).id, 1)
        await client.request('PUT', `${collection}/1`, { name: 'Changed' })
        assert.equal(JSON.parse(await run(`cat ${path}`)).name, 'Changed')
        assert.notEqual((await ws.shell(`echo invalid > ${path}`)).exitCode, 0)
        assert.notEqual((await ws.shell(`cat ${mount}/${collection}/404.json`)).exitCode, 0)
        // A missing path is ENOENT, so a test of it is false rather than an
        // error that ends the command line: an object the API answers 404
        // for, a name no endpoint serves, a directory that does not exist,
        // and a glob over an empty directory that stays literal.
        const exists = async (p) => (await run(`[ -e ${p} ] && echo yes || echo no`)).trim()
        assert.equal(await exists(path), 'yes')
        assert.equal(await exists(`${mount}/${collection}/404.json`), 'no')
        assert.equal(await exists(`${mount}/${collection}/none.json`), 'no')
        assert.equal(await exists(`${mount}/missing`), 'no')
        assert.equal(
          (
            await run(
              `for f in ${mount}/missing/*.json; do [ -e "$f" ] || continue; echo "$f"; done; echo after`,
            )
          ).trim(),
          'after',
        )
        assert.match(
          new TextDecoder().decode((await ws.shell(`ls ${mount}/missing`)).stderr),
          /No such file or directory/,
        )
        // A dropped connection is retried for a read and never for a write.
        attempts.GET = 0
        await run(`cat ${mount}/${collection}/2.json`)
        const reads = attempts.GET
        drops = 1
        attempts.GET = 0
        assert.equal(JSON.parse(await run(`cat ${mount}/${collection}/2.json`)).id, 2)
        assert.equal(attempts.GET, reads + 1)
        // So is a gateway error, but not an answer such as a 404.
        gateways = 1
        attempts.GET = 0
        assert.equal(JSON.parse(await run(`cat ${mount}/${collection}/2.json`)).id, 2)
        assert.equal(attempts.GET, reads + 1)
        attempts.GET = 0
        await assert.rejects(client.request('GET', `${collection}/404`), { status: 404 })
        assert.equal(attempts.GET, 1)
        // Three attempts are the limit, and the last failure is the one thrown.
        drops = 3
        attempts.GET = 0
        await assert.rejects(client.request('GET', `${collection}/2`), { transport: true })
        assert.equal(attempts.GET, 3)
        gateways = 3
        attempts.GET = 0
        await assert.rejects(client.request('GET', `${collection}/2`), { status: 503 })
        assert.equal(attempts.GET, 3)
        drops = 1
        attempts.PUT = 0
        await assert.rejects(client.request('PUT', `${collection}/1`, { name: 'Again' }))
        assert.equal(attempts.PUT, 1)
      } finally {
        await ws.close()
      }
    }
  } finally {
    await new Promise((resolve) => server.close(resolve))
  }
}
console.log(
  'Canvas/WooCommerce pagination, filters, auth, nested mounts, fresh reads, remote writes, missing paths and dropped reads PASS',
)
