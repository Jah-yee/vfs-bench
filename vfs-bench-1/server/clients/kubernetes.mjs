// API access only. No workspace, CLI parsing, or fixture construction.
import https from 'node:https'
import http from 'node:http'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(
  new URL('../../submodule/mirage/typescript/packages/node/package.json', import.meta.url),
)
const yaml = require('yaml')

export class KubernetesClient {
  constructor(config) {
    const kube = yaml.parse(readFileSync(config.kubeconfig, 'utf8'))
    const context = kube.contexts.find((x) => x.name === kube['current-context']).context
    const cluster = kube.clusters.find((x) => x.name === context.cluster).cluster
    const user = kube.users.find((x) => x.name === context.user)?.user ?? {}
    this.server = cluster.server
    const endpoint = new URL(this.server)
    if (endpoint.protocol === 'http:' && endpoint.hostname === '127.0.0.1') {
      this.transport = http
      this.tls = {}
    } else if (endpoint.protocol === 'https:') {
      this.transport = https
      this.tls = {
        ca: Buffer.from(cluster['certificate-authority-data'], 'base64'),
        cert: Buffer.from(user['client-certificate-data'], 'base64'),
        key: Buffer.from(user['client-key-data'], 'base64'),
      }
    } else {
      throw new Error('Kubernetes requires HTTPS or a loopback HTTP proxy')
    }
  }

  request(path) {
    return new Promise((resolve, reject) => {
      const request = this.transport.get(new URL(path, this.server), this.tls, (response) => {
        const chunks = []
        response.on('data', (chunk) => chunks.push(chunk))
        response.on('error', reject)
        response.on('end', () => {
          const body = Buffer.concat(chunks).toString('utf8')
          if (response.statusCode >= 400) {
            reject(
              Object.assign(new Error(`Kubernetes ${response.statusCode}: ${body}`), {
                status: response.statusCode,
              }),
            )
          } else {
            try {
              resolve(JSON.parse(body))
            } catch (error) {
              reject(error)
            }
          }
        })
      })
      request.setTimeout(30000, () => request.destroy(new Error('Kubernetes request timed out')))
      request.on('error', reject)
    })
  }

  async resources() {
    if (this.discovery) return this.discovery
    const groups = await this.request('/apis')
    const bases = [
      '/api/v1',
      ...groups.groups.map((group) => `/apis/${group.preferredVersion.groupVersion}`),
    ]
    const discovery = new Map()
    for (const base of bases) {
      const list = await this.request(base)
      for (const resource of list.resources) {
        if (
          !resource.name.includes('/') &&
          resource.verbs.includes('list') &&
          !discovery.has(resource.name)
        ) {
          discovery.set(resource.name, { ...resource, base })
        }
      }
    }
    this.discovery = discovery
    return discovery
  }
}
