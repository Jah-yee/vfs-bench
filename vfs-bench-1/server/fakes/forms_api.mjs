// Original Mirage Forms routes, with opaque IDs accepted by upstream graders.
import { writeFileSync } from 'node:fs'
import { serve } from '../../submodule/mirage/integ/server/kit/typescript/serve.ts'
import { DEFAULT_RUN } from '../../submodule/mirage/integ/server/kit/typescript/tenant.ts'
import { gwsFake } from '../../submodule/mirage/integ/server/gws/fake.ts'
import { GwsState } from '../../submodule/mirage/integ/server/gws/store/state.ts'

const nextId = GwsState.prototype.nextId
GwsState.prototype.nextId = function (kind) {
  if (kind === 'form') return `form${String(this.next(kind)).padStart(28, '0')}`
  return nextId.call(this, kind)
}
const server = await serve(gwsFake)
writeFileSync('/tmp/toolathlon-gws-database', server.runtime.pool.fileFor(DEFAULT_RUN))
