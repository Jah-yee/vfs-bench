// Finite native commands and port-forward startup; the harness owns lifetime.
import { clearTimeout } from 'node:timers'
import { spawn } from 'node:child_process'
import { statSync } from 'node:fs'
import { track } from './processes.mjs'
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

export function nativeCommand(name, description) {
  return new CLI({
    spec: new CommandSpec({
      name,
      description,
      arguments: [new Argument('--help', { action: 'store_true' }), TEXTS_OPERAND],
    }),
    handlers: {
      '': new CLIHandler({
        fn: async (accessor, _paths, _texts, ctx) => {
          const config = accessor.config
          const stdin = ctx.stdin == null ? null : await materialize(ctx.stdin)
          const root = config.virtualRoot || '/work'
          // A relative argument resolves where the shell has cd'd, as a real
          // shell's command's would; outside the task root it runs at the top.
          const pwd = ctx.env?.PWD ?? root
          const inside =
            pwd === root || pwd.startsWith(root + '/')
              ? config.workdir + pwd.slice(root.length)
              : config.workdir
          // A directory removed since the shell's cd runs at the root, as over SSH.
          const directory = (path) => {
            try {
              return statSync(path).isDirectory()
            } catch (error) {
              if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return false
              throw error
            }
          }
          const here = config.sshCommand || directory(inside) ? inside : config.workdir
          const args = [...ctx.argv].map((arg) => {
            const flag = arg.match(/^(--(?:filename|kustomize|patch-file|values)=)/)?.[0] || ''
            const value = arg.slice(flag.length)
            return value === root || value.startsWith(root + '/')
              ? flag + config.workdir + value.slice(root.length)
              : arg
          })
          const background = name === 'kubectl' && args.includes('port-forward')
          const result = await new Promise((resolve) => {
            if (!config.launch) throw new Error('Native execution requires harness confinement')
            const [program, ...prefix] = config.launch
            const quote = (arg) => "'" + arg.replaceAll("'", "'\\''") + "'"
            const commandArgs = config.sshCommand
              ? [
                  ...prefix,
                  // A directory the sandbox's mount has not shown yet falls back
                  // to the task root, where every command ran before.
                  `cd ${quote(here)} 2>/dev/null || cd ${quote(config.workdir)} && ` +
                    `${config.sshCommand} ${args.map(quote).join(' ')}`,
                ]
              : [
                  // Linux's sandboxes pick the directory themselves (sandlock
                  // --cwd, bwrap --chdir in server/execution.py), not spawn's.
                  ...prefix.map((arg, i) =>
                    ['--cwd', '--chdir'].includes(prefix[i - 1]) ? here : arg,
                  ),
                  ...args,
                ]
            const child = spawn(program, commandArgs, {
              detached: true,
              cwd: config.sshCommand ? config.localWorkdir : here,
              env: {
                ...config.env,
                KUBECONFIG: config.kubeconfig,
                KUBECTL_NATIVE: config.native || config.binary,
                K8S_PROCESS_DIR: config.processDir || '',
                HTTP_PROXY: 'http://127.0.0.1:9',
                HTTPS_PROXY: 'http://127.0.0.1:9',
                http_proxy: 'http://127.0.0.1:9',
                https_proxy: 'http://127.0.0.1:9',
                NO_PROXY: 'localhost,127.0.0.1,::1',
                no_proxy: 'localhost,127.0.0.1,::1',
              },
              stdio: ['pipe', 'pipe', 'pipe'],
              ...(background ? {} : { timeout: config.timeoutMs ?? 600000 }),
            })
            track(child, config.executionDir, background)
            const stdout = [],
              stderr = []
            let settled = false
            let timer
            const finish = (code) => {
              if (settled) return
              settled = true
              clearTimeout(timer)
              resolve({
                stdout: Buffer.concat(stdout),
                stderr: Buffer.concat(stderr),
                exitCode: code,
              })
            }
            child.stdout.on('data', (chunk) => {
              if (settled) return
              stdout.push(chunk)
              if (background && Buffer.concat(stdout).includes('Forwarding from')) finish(0)
            })
            child.stderr.on('data', (chunk) => {
              if (!settled) stderr.push(chunk)
            })
            child.stdin.on('error', () => {})
            child.stdin.end(stdin)
            child.on('error', (error) => {
              stderr.push(Buffer.from(error.message))
              finish(127)
            })
            child.on('close', (code) => finish(code ?? 1))
            if (background)
              timer = setTimeout(() => {
                child.kill()
                stderr.push(Buffer.from('port-forward did not become ready\n'))
                finish(1)
              }, 30000)
          })
          return [
            yieldBytes(result.stdout),
            new IOResult({ stderr: result.stderr, exitCode: result.exitCode }),
          ]
        },
      }),
    },
    configModel: (config) => config,
  })
}
