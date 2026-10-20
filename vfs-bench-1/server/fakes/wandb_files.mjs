// Large public run files stay remote. A captured content checksum controls
// which bytes can be returned, regardless of the current download URL.
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import { createServer, request } from 'node:http'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const CACHE = fileURLToPath(new URL('../../state/wandb-files/', import.meta.url))
const QUERY = `query($entity:String!,$project:String!,$run:String!,$names:[String]) {
  project(entityName:$entity,name:$project) {run(name:$run) {
    files(names:$names,first:1) {edges {node {id name md5 sizeBytes directUrl}}}
  }}}`

function verify(file, bytes) {
  if (
    createHash('md5').update(bytes).digest('base64') !== file.sourceMd5 ||
    bytes.length !== Number(file.sourceSizeBytes)
  )
    throw new Error('Public W&B file differs from the captured content checksum')
  return bytes
}

export async function content(file, fetcher = fetch) {
  const key = Buffer.from(file.sourceMd5, 'base64').toString('hex')
  const path = join(CACHE, key)
  try {
    return verify(file, await readFile(path))
  } catch (error) {
    if (error.code !== 'ENOENT') throw error
  }
  const { entity, project, run, name } = file.remote
  const response = await fetcher('https://api.wandb.ai/graphql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: QUERY, variables: { entity, project, run, names: [name] } }),
    signal: AbortSignal.timeout(120000),
  })
  if (!response.ok) throw new Error(`W&B file lookup failed: ${response.status}`)
  const body = await response.json()
  const actual = body.data?.project?.run?.files?.edges?.[0]?.node
  if (
    body.errors ||
    !actual ||
    actual.id !== file.sourceId ||
    actual.name !== name ||
    actual.md5 !== file.sourceMd5 ||
    Number(actual.sizeBytes) !== Number(file.sourceSizeBytes)
  )
    throw new Error('W&B file metadata differs from the capture')
  const download = await fetcher(actual.directUrl, { signal: AbortSignal.timeout(120000) })
  if (!download.ok) throw new Error(`W&B file download failed: ${download.status}`)
  const bytes = verify(file, Buffer.from(await download.arrayBuffer()))
  await mkdir(CACHE, { recursive: true })
  const temporary = path + '.' + randomUUID()
  await writeFile(temporary, bytes)
  await rename(temporary, path)
  return bytes
}

export async function startFiles(backend, fixture, port = 0) {
  let base
  const pending = new Map()
  const server = createServer((req, res) => {
    void handle(req, res).catch((error) => {
      res.writeHead(502, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ error: error.message }))
    })
  })
  async function handle(req, res) {
    const url = new URL(req.url, base)
    const storage = url.pathname.startsWith('/storage/')
    if (req.method === 'GET' && (storage || url.pathname.startsWith('/files/'))) {
      const authorized = storage
        ? url.searchParams.get('signature') === 'fixture' && req.headers.authorization === undefined
        : req.headers.authorization ===
          `Basic ${Buffer.from('api:0123456789abcdef0123456789abcdef01234567').toString('base64')}`
      const [entity, project, run, ...parts] = url.pathname
        .slice(storage ? 9 : 7)
        .split('/')
        .map(decodeURIComponent)
      const file = fixture.entities[entity]?.[project]?.find((row) => row.name === run)?.files[
        parts.join('/')
      ]
      if (authorized && file?.remote) {
        if (!pending.has(file.sourceId)) {
          const loading = content(file)
          pending.set(file.sourceId, loading)
          loading.catch(() => pending.delete(file.sourceId))
        }
        const bytes = await pending.get(file.sourceId)
        res.writeHead(200)
        res.end(bytes)
        return
      }
    }
    await new Promise((resolve, reject) => {
      const proxy = request(
        backend + req.url,
        { method: req.method, headers: req.headers },
        (response) => {
          const chunks = []
          response.on('data', (chunk) => chunks.push(chunk))
          response.on('error', reject)
          response.on('end', () => {
            let bytes = Buffer.concat(chunks)
            if (url.pathname === '/graphql')
              bytes = Buffer.from(bytes.toString().replaceAll(backend, base))
            const headers = { ...response.headers }
            delete headers['content-length']
            delete headers['transfer-encoding']
            res.writeHead(response.statusCode, headers)
            res.end(bytes)
            resolve()
          })
        },
      )
      proxy.on('error', reject)
      req.pipe(proxy)
    })
  }
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(port, '127.0.0.1', resolve)
  })
  base = `http://127.0.0.1:${server.address().port}`
  return {
    base,
    close: () =>
      new Promise((resolve) => {
        server.close(resolve)
        server.closeAllConnections()
      }),
  }
}
