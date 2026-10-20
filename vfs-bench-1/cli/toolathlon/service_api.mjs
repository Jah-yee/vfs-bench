// Original service tools, plus binary Canvas file transfer through stdin/stdout.
import { downloadFile, uploadFile } from '../../server/clients/canvas_files.mjs'
import { toolCommand } from './tool.mjs'
import {
  CLI,
  CLIHandler,
} from '../../submodule/mirage/typescript/packages/core/dist/commands/cli/types.js'
import {
  Argument,
  CommandSpec,
} from '../../submodule/mirage/typescript/packages/core/dist/commands/spec/types.js'
import { TEXTS_OPERAND } from '../../submodule/mirage/typescript/packages/core/dist/commands/spec/constants.js'
import {
  IOResult,
  materialize,
} from '../../submodule/mirage/typescript/packages/core/dist/io/types.js'
import { yieldBytes } from '../../submodule/mirage/typescript/packages/core/dist/io/stream.js'

export function serviceCommand(name, kind) {
  const original = toolCommand(name, kind === 'canvas' ? 'canvas_' : 'woo_')
  return new CLI({
    spec: new CommandSpec({
      name,
      description: `${kind} service reads and mutations`,
      arguments: [new Argument('--help', { action: 'store_true' }), TEXTS_OPERAND],
    }),
    handlers: {
      '': new CLIHandler({
        write: true,
        fn: async (accessor, paths, texts, ctx) => {
          try {
            const [verb, path, ...options] = ctx.argv
            if (kind === 'canvas' && ['upload', 'download'].includes(verb)) {
              if (verb === 'download') {
                if (!/^\d+$/.test(path) || options.length)
                  throw new Error('canvas download FILE_ID')
                return [yieldBytes(await downloadFile(accessor.config.files, path)), new IOResult()]
              }
              if (
                options.length &&
                (options.length !== 2 || options[0] !== '--folder' || !/^\d+$/.test(options[1]))
              )
                throw new Error('canvas upload FILENAME [--folder ID] < FILE')
              if (ctx.stdin == null) throw new Error('Pipe the file bytes to upload')
              const bytes = await materialize(ctx.stdin)
              const result = await uploadFile(accessor.config.files, path, bytes, options[1])
              return [
                yieldBytes(new TextEncoder().encode(JSON.stringify(result, null, 2) + '\n')),
                new IOResult(),
              ]
            }
            return await original.handlers[''].fn(accessor, paths, texts, ctx)
          } catch (error) {
            return [
              null,
              new IOResult({
                stderr: new TextEncoder().encode(`${name}: ${error.message}\n`),
                exitCode: 1,
              }),
            ]
          }
        },
      }),
    },
    configModel: (config) => config,
  })
}
