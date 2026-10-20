// Own the unchanged Airtable fixture's listener and its scratch database.
import { closeSync, openSync } from 'node:fs'
import { join } from 'node:path'
import { airtableFake } from '../../submodule/mirage/integ/server/airtable/fake.ts'
import {
  makeRuntime,
  createKitServer,
} from '../../submodule/mirage/integ/server/kit/typescript/http.ts'
import {
  parseFixture,
  parseFixtureRoot,
} from '../../submodule/mirage/integ/server/kit/typescript/port.ts'

const runtime = makeRuntime(airtableFake, parseFixtureRoot(process.argv.slice(2)))
// Prisma 6's macOS engine fails to create a missing SQLite file. The pinned
// kit uses this template path; creating the empty file leaves its schema and
// seeding to the kit's own db push and reset.
closeSync(openSync(join(runtime.pool.root, '.templates', 'schema.db'), 'wx'))
await runtime.reset({ fixture: parseFixture(process.argv.slice(2)) })
const server = createKitServer(runtime)
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
console.log(`AIRTABLE_URL=http://127.0.0.1:${server.address().port}`)
const close = async () => {
  server.closeAllConnections()
  await new Promise((resolve) => server.close(resolve))
  await runtime.dispose()
  process.exit(0)
}
process.once('SIGINT', close)
process.once('SIGTERM', close)
