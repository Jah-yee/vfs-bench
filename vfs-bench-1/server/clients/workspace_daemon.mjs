// Host-owned initialization uses Mirage's local configuration API. The REST
// create route continues to reject executable runtime initialization hooks.
import { pathToFileURL } from 'node:url'
const { buildApp, buildWorkspaceFromConfig } = await import(pathToFileURL(process.argv[2]).href)
const workspace = await buildWorkspaceFromConfig(process.argv[3])
let stopping = false
const stop = () => {
  if (stopping) return
  stopping = true
  void app.close().finally(() => process.exit(0))
}
const app = buildApp({ onIdleExit: stop })
app.registry.add(workspace, workspace.workspaceId)
process.on('SIGTERM', stop)
process.on('SIGINT', stop)
await app.listen({ port: Number(process.env.MIRAGE_DAEMON_PORT), host: '127.0.0.1' })
