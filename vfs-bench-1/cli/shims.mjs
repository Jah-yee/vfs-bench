// The out-of-tree CLIs a task's `clis:` block can name, as mirage's own
// config already resolves them.
//
// A `cli:` value carrying a colon points at code -- `./tool.mjs:TALLY` --
// and `absolutizeCodeRef` rebases the path onto the config file's own
// directory, so a task writes `cli: ../../../../cli/shims.mjs:COOK` and
// `buildWorkspaceFromConfig` does the rest. Nothing here is registered by
// hand.
//
// Each export is a Node CLI whose one leaf spawns the Python program of the
// same name beside this file. The CLI an agent types is Python: one spec
// and one set of queries in `cli/*_cli.py`, which is the same file the
// parity suite compares against upstream's MCP server. Two implementations
// would be two things to keep equal.
//
// `configModel` is the identity normalizer rather than a zod schema: the
// values are validated in the subprocess, whose own CLI declares a
// `config_model`, and validating them twice in two languages is two places
// for the rule to live.

import { spawn } from 'node:child_process'
import { track } from './processes.mjs'
import { fileURLToPath } from 'node:url'

// Resolved against this file rather than imported by package name: the
// submodule is a pnpm workspace whose links live inside it, so a bare
// specifier would need an install step in cli/ that duplicates it.
const PACKAGES = process.env.MIRAGE_PACKAGES
  ? new URL(`file://${process.env.MIRAGE_PACKAGES.replace(/\/?$/, '/')}`)
  : new URL('../submodule/mirage/typescript/packages/', import.meta.url)
// Every core symbol from the module that declares it, never from the
// barrel. core's index re-exports a shifting subset, so a barrel import
// breaks on a pin bump with `X is not a constructor` from a line that
// never mentions X. The `./*` subpath is core's own public export map.
const CORE = (path) => import(new URL(`core/dist/${path}`, PACKAGES).href)
const { CLI, CLIHandler } = await CORE('commands/cli/types.js')
const { Argument, CommandSpec } = await CORE('commands/spec/types.js')
const { TEXTS_OPERAND } = await CORE('commands/spec/constants.js')
const { IOResult, materialize } = await CORE('io/types.js')
const { yieldBytes } = await CORE('io/stream.js')

const PYTHON = process.env.SHIM_PYTHON ?? 'python3'

// Each shim's program sits beside this file, so it is resolved from this
// file's own URL rather than from an environment variable the harness
// exports. Nothing about which program to spawn then depends on how the
// process that imports this was launched -- which is what a long-lived
// daemon would get wrong, having been started once for every task.
// `entry` in a task's `config:` block still wins, which is how
// nhl-b2b-analysis reaches its task-local `gsheet`.
const beside = (name) => fileURLToPath(new URL(name, import.meta.url))

function runPython(name, entry, env, argv, stdin, executionDir) {
  return new Promise((resolve) => {
    // stdin is piped rather than ignored so a shim can take a body on a
    // pipe rather than translate an agent's virtual path into a host one.
    const proc = spawn(PYTHON, [entry, ...argv], {
      env: { ...process.env, ...env },
      stdio: ['pipe', 'pipe', 'pipe'],
      detached: true,
    })
    track(proc, executionDir)
    proc.stdin.on('error', () => {})
    if (stdin !== null && stdin.length > 0) proc.stdin.write(Buffer.from(stdin))
    proc.stdin.end()
    const out = []
    const err = []
    proc.stdout.on('data', (chunk) => out.push(chunk))
    proc.stderr.on('data', (chunk) => err.push(chunk))
    proc.on('error', (error) => {
      resolve([new Uint8Array(), Buffer.from(`${name}: ${error.message}\n`), 127])
    })
    proc.on('close', (code) => {
      resolve([Buffer.concat(out), Buffer.concat(err), code ?? 1])
    })
  })
}

// `entry` names an environment variable that may override which module to
// spawn, and `config` maps each key a task may write under
// `clis: <name>: config:` to the variable the subprocess reads it from.
// The task's yaml wins over the ambient variable, which is the fallback
// for a direct invocation -- and a shared daemon has no per-task
// environment, so a task that needs a value writes it in its own config.
function shim(name, description, entry, config, behavior = {}) {
  return new CLI({
    spec: new CommandSpec({
      name,
      description,
      // Declaring --help keeps mirage from injecting and answering its own:
      // these specs have no grammar to render a page from, and Python does.
      // A `str` rest operand makes the parser lenient about undeclared dashed
      // tokens, so every flag, verb, refusal and --help page is decided by
      // the Python side.
      arguments: [new Argument('--help', { action: 'store_true' }), TEXTS_OPERAND],
    }),
    handlers: {
      '': new CLIHandler({
        write: behavior.write ?? false,
        fn: async (accessor, _paths, _texts, ctx) => {
          const program = accessor.config?.entry ?? process.env[entry] ?? beside(`${name}_main.py`)
          const env = {}
          for (const [key, variable] of Object.entries(config)) {
            const value = accessor.config?.[key] ?? process.env[variable]
            if (value !== undefined) env[variable] = String(value)
          }
          const piped =
            ctx.stdin === null || ctx.stdin === undefined ? null : await materialize(ctx.stdin)
          const [stdout, stderr, exitCode] = await runPython(
            name,
            program,
            env,
            [...ctx.argv],
            piped,
            accessor.config?.executionDir,
          )
          return [
            yieldBytes(new Uint8Array(stdout)),
            new IOResult({ stderr: new Uint8Array(stderr), exitCode }),
          ]
        },
      }),
    },
    configModel: (input) => input,
  })
}

export const COOK = shim('cook', 'Look up Chinese home-cooking recipes', 'COOK_ENTRY', {
  corpus: 'HOWTOCOOK_CORPUS',
})
// Task-local: only nhl-b2b-analysis mounts it, and there is no
// `gsheet_main.py` beside this file, so its yaml names the program under
// its own `vfs/cli/` as `entry:`. Five config keys where the rest take
// one.
export const GSHEET = shim(
  'gsheet',
  'Change a Google spreadsheet (read one through /gd)',
  'GSHEET_ENTRY',
  {
    client_id: 'GSHEET_CLIENT_ID',
    client_secret: 'GSHEET_CLIENT_SECRET',
    refresh_token: 'GSHEET_REFRESH_TOKEN',
    api_base: 'GWS_URL',
    folder_id: 'DRIVE_FOLDER_ID',
  },
  // Every verb in the task-local gsheet tree mutates Sheets. The Python
  // process cannot carry its CLIHandler metadata across the process boundary,
  // so repeat it on the host wrapper. Mirage invalidates account-backed
  // mount caches after a successful write.
  { write: true },
)
