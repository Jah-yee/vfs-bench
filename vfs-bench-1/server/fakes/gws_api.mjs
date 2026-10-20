// Start Mirage's unchanged fixture and expose its database path to the
// owning harness. This file is never part of the agent's workspace.
import { writeFileSync } from 'node:fs'
import { serve } from '../../submodule/mirage/integ/server/kit/typescript/serve.ts'
import { DEFAULT_RUN } from '../../submodule/mirage/integ/server/kit/typescript/tenant.ts'
import { gwsFake } from '../../submodule/mirage/integ/server/gws/fake.ts'
import { dropState } from '../../submodule/mirage/integ/server/gws/store/cache.ts'

// The harness restores SQLite snapshots outside the API between requests.
// Mirage caches request state, so this transport must reload the authoritative
// rows before invoking an unchanged handler, including the first post-restore
// write. Otherwise that write can overwrite the restored snapshot.
const server = await serve({
  ...gwsFake,
  routes: () =>
    gwsFake.routes().map((route) => ({
      ...route,
      handler: (context) => {
        dropState(context.db, context.tenant)
        return route.handler(context)
      },
    })),
})
writeFileSync('/tmp/toolathlon-gws-database', server.runtime.pool.fileFor(DEFAULT_RUN))
