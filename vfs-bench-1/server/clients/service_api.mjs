// REST transport only; API permissions and mutations remain service-owned.
import http from 'node:http'
import https from 'node:https'

// A read whose connection drops before an answer, or that a tunnel answers
// with a gateway error, is sent again; the e2b tunnel resets connections
// under a burst of reads. A write is never resent, since it may have landed.
const READ_ATTEMPTS = 3
const GATEWAY = new Set([502, 503, 504])

export class ServiceClient {
  constructor(config) {
    this.base = config.apiBase.replace(/\/$/, '')
    this.kind = config.kind
    this.headers =
      this.kind === 'canvas'
        ? { Authorization: `Bearer ${config.token}` }
        : {
            Authorization: `Basic ${Buffer.from(`${config.key}:${config.secret}`).toString('base64')}`,
          }
    this.insecure = config.insecure === true
  }
  async request(method, path, data, query = {}) {
    for (let attempt = 1; ; attempt++) {
      try {
        return await this.send(method, path, data, query)
      } catch (error) {
        const transient = error.transport || GATEWAY.has(error.status)
        if (method !== 'GET' || !transient || attempt === READ_ATTEMPTS) throw error
        await new Promise((resolve) => setTimeout(resolve, 250 * 2 ** (attempt - 1)))
      }
    }
  }
  async send(method, path, data, query) {
    const url = new URL(this.base + '/' + path.replace(/^\//, ''))
    for (const [key, value] of Object.entries(query)) {
      for (const item of Array.isArray(value) ? value : [value])
        url.searchParams.append(key, String(item))
    }
    const body = data === undefined ? undefined : Buffer.from(JSON.stringify(data))
    return new Promise((resolve, reject) => {
      const transport = url.protocol === 'https:' ? https : http
      const request = transport.request(
        url,
        {
          method,
          rejectUnauthorized: !this.insecure,
          headers: {
            ...this.headers,
            Accept: 'application/json',
            ...(body ? { 'Content-Type': 'application/json', 'Content-Length': body.length } : {}),
          },
        },
        (response) => {
          const chunks = []
          let errorBytes = 0
          response.on('data', (chunk) => {
            // Rails error pages may include megabytes of HTML. Bound error
            // storage as well as the message delivered to the model.
            if (response.statusCode < 400) chunks.push(chunk)
            else if (errorBytes < 4096) {
              chunks.push(chunk.subarray(0, 4096 - errorBytes))
              errorBytes += chunk.length
            }
          })
          response.on('error', (error) => reject(Object.assign(error, { transport: true })))
          response.on('end', () => {
            const raw = Buffer.concat(chunks).toString('utf8')
            if (response.statusCode >= 400) {
              let detail = response.statusMessage || 'Request failed'
              try {
                const error = JSON.parse(raw)
                detail = error.message || error.error || error.errors || detail
                if (typeof detail !== 'string') detail = JSON.stringify(detail)
              } catch {
                if (!/<(?:!doctype|html|body)/i.test(raw)) detail = raw || detail
              }
              return reject(
                Object.assign(
                  new Error(`${this.kind} ${response.statusCode}: ${detail.slice(0, 200)}`),
                  { status: response.statusCode },
                ),
              )
            }
            if (response.statusCode >= 300)
              return reject(
                new Error(`${this.kind}: unexpected redirect to ${response.headers.location}`),
              )
            try {
              resolve({ data: raw ? JSON.parse(raw) : null, headers: response.headers })
            } catch (error) {
              reject(error)
            }
          })
        },
      )
      request.on('error', (error) => reject(Object.assign(error, { transport: true })))
      request.setTimeout(30000, () => request.destroy(new Error(`${this.kind} API timed out`)))
      request.end(body)
    })
  }
  async list(path, query = {}) {
    const rows = []
    for (let page = 1; ; page++) {
      const result = await this.request('GET', path, undefined, { per_page: 100, ...query, page })
      const batch = Array.isArray(result.data)
        ? result.data
        : this.kind === 'canvas'
          ? (result.data?.quiz_submissions ?? result.data?.quiz_submission_questions)
          : undefined
      if (!Array.isArray(batch)) throw new Error(`Expected an API collection: ${path}`)
      rows.push(...batch)
      const next = /<[^>]+>;\s*rel="next"/.test(result.headers.link || '')
      const pages = Number(result.headers['x-wp-totalpages'])
      if (!next && !(pages > page)) return rows
    }
  }
}
