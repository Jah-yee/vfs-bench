import { ServiceVFS } from './service_api.mjs'
import { enoent } from '../submodule/mirage/typescript/packages/core/dist/errors/fs.js'

export class WooCommerceVFS extends ServiceVFS {
  constructor(config) {
    super({ ...config, kind: 'woocommerce' })
  }
  endpoint(path) {
    if (!/^(products|orders|customers|categories)(\/\d+)?(\/variations(\/\d+)?)?$/.test(path))
      throw enoent(path)
    if (path.includes('/variations') && !/^products\/\d+\/variations/.test(path)) throw enoent(path)
    return path.replace(/^categories(?=\/|$)/, 'products/categories')
  }
  async listing(path) {
    if (!path) return ['products', 'orders', 'customers', 'categories']
    if (/^products\/\d+$/.test(path)) {
      await this.client.request('GET', this.endpoint(path))
      return ['variations']
    }
    const rows = await this.client.list(this.endpoint(path))
    return rows.flatMap((row) => [
      `${row.id}.json`,
      ...(/^products$/.test(path) && row.type === 'variable' ? [String(row.id)] : []),
    ])
  }
}
