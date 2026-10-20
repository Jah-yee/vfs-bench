// The original tasks distinguish spreadsheet IDs from names by their Google
// shape. Keep the fixture counter deterministic while minting opaque file IDs.
import { createHash } from 'node:crypto'
import { serve } from '../../submodule/mirage/integ/server/kit/typescript/serve.ts'
import { gwsFake } from '../../submodule/mirage/integ/server/gws/fake.ts'
import { GwsState } from '../../submodule/mirage/integ/server/gws/store/state.ts'

const nextId = GwsState.prototype.nextId
GwsState.prototype.nextId = function (kind) {
  const id = nextId.call(this, kind)
  return kind === 'f' || kind === 'sheet'
    ? `1${createHash('sha256').update(id).digest('base64url')}`
    : id
}

await serve(gwsFake)
