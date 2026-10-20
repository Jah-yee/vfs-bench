// A read-only file view of live API objects. Mutations belong to the CLI.
import { KubernetesClient } from '../server/clients/kubernetes.mjs'
import { BaseVFS } from '../submodule/mirage/typescript/packages/core/dist/vfs/base.js'
import {
  FileStat,
  FileType,
  ContentType,
} from '../submodule/mirage/typescript/packages/core/dist/types.js'
import {
  eacces,
  enoent,
  eisdir,
  isEnoent,
} from '../submodule/mirage/typescript/packages/core/dist/errors/fs.js'

export class KubernetesVFS extends BaseVFS {
  name = 'kubernetes'
  indexTtl = 0
  cachesReads = false
  maxDuEntries = 1000
  prompt =
    'Kubernetes API objects as JSON. /namespaces/<namespace>/<resource>/<name>.json and /cluster/<resource>/<name>.json. Read-only; use kubectl for changes.'

  constructor(config) {
    super()
    this.client = new KubernetesClient(config)
  }
  getState() {
    return { type: this.name, needs_override: true }
  }
  parts(path) {
    return path.vfsPath.split('/').filter(Boolean)
  }

  async endpoint(parts) {
    const namespaced = parts[0] === 'namespaces'
    if ((!namespaced && parts[0] !== 'cluster') || parts.length !== (namespaced ? 3 : 2)) {
      throw enoent(parts.join('/'))
    }
    const type = parts[namespaced ? 2 : 1]
    const resource = (await this.client.resources()).get(type)
    if (!resource || resource.namespaced !== namespaced) throw enoent(parts.join('/'))
    const scope = namespaced ? `/namespaces/${encodeURIComponent(parts[1])}` : ''
    return `${resource.base}${scope}/${resource.name}`
  }

  async readdir(path) {
    path = path.pattern ? path.dir : path
    const names = await this.filesystemCall(path, () => this.listing(path))
    return names.map((name) => this.entry(name))
  }

  // A path no resource serves, or an object the API answers 404 for, is
  // ENOENT, so a test of it is false rather than an error that ends the
  // command line; a refused credential is EACCES.
  async filesystemCall(path, operation) {
    try {
      return await operation()
    } catch (error) {
      if (error.status === 404 || isEnoent(error)) throw enoent(path)
      if (error.status === 401 || error.status === 403) throw eacces(path)
      throw error
    }
  }

  async listing(path) {
    const parts = this.parts(path)
    if (!parts.length) return ['namespaces', 'cluster']
    if (parts[0] === 'namespaces' && parts.length === 1) {
      return (await this.client.request('/api/v1/namespaces')).items
        .map((x) => x.metadata.name)
        .sort()
    }
    if (
      (parts[0] === 'namespaces' && parts.length === 2) ||
      (parts[0] === 'cluster' && parts.length === 1)
    ) {
      const namespaced = parts[0] === 'namespaces'
      if (namespaced)
        await this.client.request(`/api/v1/namespaces/${encodeURIComponent(parts[1])}`)
      return [...(await this.client.resources()).values()]
        .filter((x) => x.namespaced === namespaced)
        .map((x) => x.name)
        .sort()
    }
    const result = await this.client.request(await this.endpoint(parts))
    return result.items.map((x) => `${x.metadata.name}.json`).sort()
  }

  async read(path) {
    const parts = this.parts(path)
    const name = parts.pop()
    if (!name?.endsWith('.json')) throw eisdir(path)
    const object = await this.filesystemCall(path, async () =>
      this.client.request(`${await this.endpoint(parts)}/${encodeURIComponent(name.slice(0, -5))}`),
    )
    return new TextEncoder().encode(JSON.stringify(object, null, 2) + '\n')
  }

  async stat(path) {
    const parts = this.parts(path)
    const name = parts.at(-1) || '/'
    const file = name.endsWith('.json')
    if (file) await this.read(path)
    else await this.readdir(path)
    return this.entry(name)
  }

  entry(name) {
    const file = name.endsWith('.json')
    return new FileStat({
      name,
      type: file ? FileType.FILE : FileType.DIRECTORY,
      size: file ? null : 0,
      content: file ? ContentType.JSON : null,
    })
  }
}
