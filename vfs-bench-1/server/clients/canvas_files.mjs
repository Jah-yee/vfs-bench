// Canvas's native two-step upload, with file bytes supplied by the workspace.
import http from 'node:http'
import https from 'node:https'
import { randomUUID } from 'node:crypto'
import { createRequire } from 'node:module'
import { ServiceClient } from './service_api.mjs'

// Use the MIME database from the pinned dependency tree of the native uploader.
const require = createRequire(new URL('../../vendor/canvas-mcp/package.json', import.meta.url))
const mime = require('mime-types')

async function transfer(config, address, method = 'GET', body, headers = {}, redirects = 0) {
  const url = new URL(address, config.apiBase)
  // These are the original Canvas fixture ports, forwarded from its owned sandbox.
  if (!['localhost', '127.0.0.1'].includes(url.hostname) || !['10001', '20001'].includes(url.port))
    throw new Error('Canvas file URL points outside the task fixture')
  if (redirects > 5) throw new Error('Too many Canvas file redirects')
  return new Promise((resolve, reject) => {
    const req = (url.protocol === 'https:' ? https : http).request(
      url,
      {
        method,
        rejectUnauthorized: config.insecure !== true,
        headers: { ...headers, ...(body ? { 'Content-Length': body.length } : {}) },
      },
      (res) => {
        const chunks = []
        let errorBytes = 0
        res.on('data', (chunk) => {
          if (res.statusCode < 400) chunks.push(chunk)
          else if (errorBytes < 4096) {
            chunks.push(chunk.subarray(0, 4096 - errorBytes))
            errorBytes += chunk.length
          }
        })
        res.on('error', reject)
        res.on('end', () => {
          if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            resolve(
              transfer(
                config,
                new URL(res.headers.location, url),
                [307, 308].includes(res.statusCode) ? method : 'GET',
                [307, 308].includes(res.statusCode) ? body : undefined,
                [307, 308].includes(res.statusCode)
                  ? headers
                  : Object.fromEntries(
                      Object.entries(headers).filter(([name]) => !/^content-/i.test(name)),
                    ),
                redirects + 1,
              ),
            )
            return
          }
          const bytes = Buffer.concat(chunks)
          if (res.statusCode >= 400) {
            const raw = bytes.toString()
            const detail = /<(?:!doctype|html|body)/i.test(raw) ? res.statusMessage : raw
            reject(new Error(`Canvas file ${res.statusCode}: ${(detail || '').slice(0, 200)}`))
          } else resolve(bytes)
        })
      },
    )
    req.on('error', reject)
    req.setTimeout(60000, () => req.destroy(new Error('Canvas file transfer timed out')))
    req.end(body)
  })
}

export async function downloadFile(config, id) {
  const client = new ServiceClient({ ...config, kind: 'canvas' })
  const { data } = await client.request('GET', `files/${id}`)
  return transfer(config, data.url)
}

export async function uploadFile(config, target, bytes, folder) {
  const client = new ServiceClient({ ...config, kind: 'canvas' })
  if (!target || /[\r\n"/\\]/.test(target)) throw new Error('Specify a plain upload filename')
  const endpoint = folder ? `folders/${folder}/files` : 'users/self/files'
  const { data } = await client.request('POST', endpoint, {
    name: target,
    size: bytes.length,
    on_duplicate: 'rename',
  })
  const boundary = `canvas-${randomUUID()}`
  const chunks = []
  for (const [name, value] of Object.entries(data.upload_params)) {
    if (/[\r\n"]/.test(name)) throw new Error('Invalid Canvas upload field')
    chunks.push(
      Buffer.from(
        `--${boundary}\r\nContent-Disposition: form-data; name="${name}"\r\n\r\n${value}\r\n`,
      ),
    )
  }
  chunks.push(
    Buffer.from(
      `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${target}"\r\nContent-Type: ${mime.lookup(target) || 'application/octet-stream'}\r\n\r\n`,
    ),
  )
  chunks.push(Buffer.from(bytes), Buffer.from(`\r\n--${boundary}--\r\n`))
  let result = JSON.parse(
    (
      await transfer(config, data.upload_url, 'POST', Buffer.concat(chunks), {
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
      })
    ).toString(),
  )
  if (result.location)
    result = JSON.parse(
      (await transfer(config, result.location, 'GET', undefined, client.headers)).toString(),
    )
  return result
}
