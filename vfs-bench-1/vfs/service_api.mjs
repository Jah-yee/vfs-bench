import { ServiceClient } from '../server/clients/service_api.mjs'
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

export class ServiceVFS extends BaseVFS {
  indexTtl = 0
  cachesReads = false
  maxDuEntries = 10000
  constructor(config) {
    const name = config.kind
    super({
      name,
      prompt: `${name} API objects as JSON. Read-only files; use the separate ${name === 'woocommerce' ? 'woo' : 'canvas'} CLI for mutations.`,
    })
    this.client = new ServiceClient(config)
  }
  getState() {
    return { type: this.name, needs_override: true }
  }
  path(path) {
    return path.vfsPath.split('/').filter(Boolean).join('/')
  }
  async readdir(path) {
    path = path.pattern ? path.dir : path
    const names = await this.filesystemCall(path, () => this.listing(this.path(path)))
    return names.map((name) => this.entry(name))
  }
  async filesystemCall(path, operation) {
    try {
      return await operation()
    } catch (error) {
      if (error.status === 404 || isEnoent(error)) throw enoent(path)
      if (error.status === 401 || error.status === 403) throw eacces(path)
      throw error
    }
  }
  async read(path) {
    const relative = this.path(path)
    if (!relative.endsWith('.json')) throw eisdir(path)
    const data = await this.filesystemCall(path, () => this.object(relative.slice(0, -5)))
    return new TextEncoder().encode(JSON.stringify(data, null, 2) + '\n')
  }
  async object(path) {
    return (await this.client.request('GET', this.endpoint(path))).data
  }
  async stat(path) {
    const name = this.path(path).split('/').at(-1) || '/'
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
