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
import { runBrowser } from './browser-client.mjs'

export const BROWSER = new CLI({
  spec: new CommandSpec({
    name: 'browser',
    description: 'The original browser tools; browser_<name> maps to browser <name>',
    arguments: [new Argument('--help', { action: 'store_true' }), TEXTS_OPERAND],
  }),
  handlers: {
    '': new CLIHandler({
      fn: async (accessor, _paths, _texts, ctx) => {
        const result = await runBrowser(
          ctx.argv,
          accessor.config.apiBase,
          accessor.config.timeoutMs,
        )
        return [
          result.stdout ? yieldBytes(new TextEncoder().encode(result.stdout)) : null,
          new IOResult({
            stderr: new TextEncoder().encode(result.stderr),
            exitCode: result.exitCode,
          }),
        ]
      },
    }),
  },
  configModel: (config) => config,
})
