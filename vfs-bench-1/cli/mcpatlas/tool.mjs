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
import { renderToolResult } from '../tool-client.mjs'

// An Atlas tool as the shell spells it: less the server's prefix, its
// underscores hyphens, so `wikipedia_search_wikipedia` is
// `wikipedia search-wikipedia`.
export function command(tool, prefix = '') {
  return (tool.startsWith(prefix) ? tool.slice(prefix.length) : tool).replaceAll('_', '-')
}

async function runTool(service, argv, apiBase, timeoutMs, prefix) {
  try {
    if (!apiBase) throw new Error(`${service} session is not running`)
    const [name, ...args] = argv
    const signal = () => (timeoutMs == null ? undefined : globalThis.AbortSignal.timeout(timeoutMs))
    const response = await fetch(`${apiBase}/tools`, { signal: signal() })
    if (!response.ok) throw new Error(`${service}: HTTP ${response.status}`)
    const originals = new Map()
    const tools = (await response.json()).tools.map((tool) => {
      const shown = command(tool.name, prefix)
      originals.set(shown, tool.name)
      return { ...tool, name: shown }
    })
    if (!name || name === '--help') {
      return {
        stdout:
          `${service} <command> ['<JSON arguments>']\nUse ${service} <command> --help for the original argument schema.\n` +
          tools.map((tool) => `${tool.name}: ${tool.description}`).join('\n') +
          '\n',
        stderr: '',
        exitCode: 0,
      }
    }
    if (!originals.has(name)) throw new Error(`Unknown ${service} command: ${name}`)
    if (args.length === 1 && args[0] === '--help') {
      const tool = tools.find((tool) => tool.name === name)
      return { stdout: JSON.stringify(tool, null, 2) + '\n', stderr: '', exitCode: 0 }
    }
    if (args.length > 1) throw new Error('Pass arguments as one JSON object')
    const parameters = JSON.parse(args[0] || '{}')
    // Upstream's harness turns the Met's image off on every call before it
    // runs one (`prunedTools` in agent-harness's agent-eval.ts), so the MCP
    // arm never receives it.
    if (service === 'met-museum' && originals.get(name) === 'get-museum-object') {
      parameters.returnImage = false
    }
    const called = await fetch(`${apiBase}/call`, {
      signal: signal(),
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: originals.get(name), arguments: parameters }),
    })
    const result = await called.json()
    if (!called.ok) throw new Error(result.error || `${service}: HTTP ${called.status}`)
    return { stdout: renderToolResult(result), stderr: '', exitCode: result.isError ? 1 : 0 }
  } catch (error) {
    return { stdout: '', stderr: `${error.message}\n`, exitCode: 1 }
  }
}

export function toolCommand(name, prefix = '', behavior = {}) {
  return new CLI({
    spec: new CommandSpec({
      name,
      description: `${name} <tool-name> '<JSON arguments>'`,
      arguments: [new Argument('--help', { action: 'store_true' }), TEXTS_OPERAND],
    }),
    handlers: {
      '': new CLIHandler({
        write: behavior.write ?? false,
        fn: async (accessor, _paths, _texts, ctx) => {
          const result = await runTool(
            name,
            ctx.argv,
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
