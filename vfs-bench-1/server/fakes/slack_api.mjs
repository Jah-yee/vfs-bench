// Own the unchanged Slack fixture's listener and its scratch database.
import { closeSync, openSync } from 'node:fs'
import { join } from 'node:path'
import { slackFake } from '../../submodule/mirage/integ/server/slack/fake.ts'
import {
  makeRuntime,
  createKitServer,
} from '../../submodule/mirage/integ/server/kit/typescript/http.ts'
import {
  parseFixture,
  parseFixtureRoot,
} from '../../submodule/mirage/integ/server/kit/typescript/port.ts'

const runtime = makeRuntime(slackFake, parseFixtureRoot(process.argv.slice(2)))
// The same Prisma 6 template workaround as notion_api.mjs.
closeSync(openSync(join(runtime.pool.root, '.templates', 'schema.db'), 'wx'))
await runtime.reset({ fixture: parseFixture(process.argv.slice(2)) })
const server = createKitServer(runtime)
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
console.log(`SLACK_URL=http://127.0.0.1:${server.address().port}`)
const close = async () => {
  server.closeAllConnections()
  await new Promise((resolve) => server.close(resolve))
  await runtime.dispose()
  process.exit(0)
}
process.once('SIGINT', close)
process.once('SIGTERM', close)
