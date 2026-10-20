// Reuse the fake Hub's captured upstream schemas and handlers for discovery.
import { commandName, parseArguments, renderToolResult } from './tool-client.mjs'
import { Client } from '../../vendor/fetch-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js'
import { StreamableHTTPClientTransport } from '../../vendor/fetch-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/streamableHttp.js'
import {
  CLI,
  CLIHandler,
} from '../../submodule/mirage/typescript/packages/core/dist/commands/cli/types.js'
import {
  Argument,
  CommandSpec,
} from '../../submodule/mirage/typescript/packages/core/dist/commands/spec/types.js'
import { TEXTS_OPERAND } from '../../submodule/mirage/typescript/packages/core/dist/commands/spec/constants.js'
import { IOResult } from '../../submodule/mirage/typescript/packages/core/dist/io/types.js'
import { yieldBytes } from '../../submodule/mirage/typescript/packages/core/dist/io/stream.js'

export const HUB = new CLI({
  spec: new CommandSpec({
    name: 'huggingface',
    description: 'Discover and inspect Hugging Face repositories',
    arguments: [new Argument('--help', { action: 'store_true' }), TEXTS_OPERAND],
  }),
  handlers: {
    '': new CLIHandler({
      fn: async (accessor, _paths, _texts, ctx) => {
        const client = new Client({ name: 'vfs-huggingface', version: '1.0.0' })
        const options = { timeout: accessor.config.timeoutMs }
        try {
          await client.connect(
            new StreamableHTTPClientTransport(new URL(accessor.config.endpoint), {
              requestInit: {
                headers: accessor.config.token
                  ? { Authorization: `Bearer ${accessor.config.token}` }
                  : {},
              },
            }),
            options,
          )
          const [name, ...args] = ctx.argv
          // The command typed may be spelled with underscores or hyphens.
          const listed = async () => (await client.listTools(undefined, options)).tools
          const find = (tools) => tools.find((tool) => commandName(tool.name) === commandName(name))
          const shown = (tool) => ({ ...tool, name: commandName(tool.name) })
          let text
          if (!name || name === '--help' || args[0] === '--help') {
            const tools = await listed()
            const tool = args[0] === '--help' ? find(tools) : tools
            if (!tool) throw new Error(`Unknown Hub tool: ${name}`)
            text = JSON.stringify(Array.isArray(tool) ? tool.map(shown) : shown(tool), null, 2)
          } else {
            if (args.length > 1) throw new Error('Pass arguments as one JSON object')
            const parameters = parseArguments(args[0] || '{}')
            // A command no tool answers to goes to the server as typed.
            const result = await client.callTool(
              { name: find(await listed())?.name ?? name, arguments: parameters },
              undefined,
              options,
            )
            const bytes = new TextEncoder().encode(renderToolResult(result))
            // A failed call's text is its error, as in tool-client.mjs.
            return result.isError
              ? [null, new IOResult({ stderr: bytes, exitCode: 1 })]
              : [yieldBytes(bytes), new IOResult()]
          }
          return [yieldBytes(new TextEncoder().encode(text + '\n')), new IOResult()]
        } catch (error) {
          return [
            null,
            new IOResult({ stderr: new TextEncoder().encode(error.message + '\n'), exitCode: 1 }),
          ]
        } finally {
          await client.close()
        }
      },
    }),
  },
  configModel: (config) => config,
})
