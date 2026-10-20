import {
  CLI,
  CLIHandler,
} from '../submodule/mirage/typescript/packages/core/dist/commands/cli/types.js'
import {
  Argument,
  CommandSpec,
} from '../submodule/mirage/typescript/packages/core/dist/commands/spec/types.js'
import { TEXTS_OPERAND } from '../submodule/mirage/typescript/packages/core/dist/commands/spec/constants.js'
import {
  IOResult,
  materialize,
} from '../submodule/mirage/typescript/packages/core/dist/io/types.js'
import { yieldBytes } from '../submodule/mirage/typescript/packages/core/dist/io/stream.js'
import { runTool } from './tool-client.mjs'

export function toolCommand(name, prefix = '', behavior = {}) {
  return new CLI({
    spec: new CommandSpec({
      name,
      description: `${name} <original-tool-name> '<JSON arguments>'`,
      arguments: [new Argument('--help', { action: 'store_true' }), TEXTS_OPERAND],
    }),
    handlers: {
      '': new CLIHandler({
        write: behavior.write ?? false,
        fn: async (accessor, _paths, _texts, ctx) => {
          const result = await runTool(
            name,
            ctx.argv,
            async () =>
              ctx.stdin == null ? '' : new TextDecoder().decode(await materialize(ctx.stdin)),
            accessor.config.apiBase,
            accessor.config.timeoutMs,
            prefix,
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
}
