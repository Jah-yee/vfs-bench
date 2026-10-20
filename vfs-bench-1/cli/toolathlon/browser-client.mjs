// A tool's command: its name less `browser_`, with hyphens for underscores,
// so `browser_tab_list` is `browser tab-list`. Written out here because the
// native E2B command copies this file alone.
const commandName = (tool) => tool.replace(/^browser_/, '').replaceAll('_', '-')

// tool-client.mjs's parseArguments, written out for the same reason: a
// function typed over several lines carries raw line breaks.
const parseArguments = (text) =>
  JSON.parse(
    text.replace(/"(?:[^"\\]|\\[^])*"/g, (string) =>
      string.replace(/\\[^]|[\0-\x1f]/g, (match) =>
        match.length > 1 ? match : `\\u${match.charCodeAt(0).toString(16).padStart(4, '0')}`,
      ),
    ),
  )

// Used by both Mirage's CLI and the native E2B command.
export async function runBrowser(argv, apiBase, timeoutMs) {
  try {
    if (!apiBase) throw new Error('Browser session is not running')
    const signal = timeoutMs == null ? undefined : globalThis.AbortSignal.timeout(timeoutMs)
    const [command, ...args] = argv
    const getTools = async () => {
      const response = await fetch(`${apiBase}/tools`, { signal })
      if (!response.ok) throw new Error(`Browser transport returned HTTP ${response.status}`)
      return (await response.json()).tools
    }
    if (!command || command === '--help') {
      const tools = await getTools()
      return {
        stdout:
          "browser <command> ['<JSON arguments>']\n" +
          'Use browser <command> --help for the original argument schema.\n' +
          tools.map((tool) => `${commandName(tool.name)}: ${tool.description}`).join('\n') +
          '\n',
        stderr: '',
        exitCode: 0,
      }
    }
    // The command typed, spelled with underscores or hyphens.
    const find = (tools) =>
      tools.find((tool) => commandName(tool.name) === command.replaceAll('_', '-'))
    if (args.length === 1 && args[0] === '--help') {
      const tool = find(await getTools())
      if (!tool) throw new Error(`Unknown browser command: ${command}`)
      return {
        stdout: JSON.stringify({ ...tool, name: commandName(tool.name) }, null, 2) + '\n',
        stderr: '',
        exitCode: 0,
      }
    }
    if (args.length > 1) throw new Error('Pass arguments as one JSON object')
    const parameters = parseArguments(args[0] || '{}')
    // A command no tool answers to goes to the server as typed.
    const name = find(await getTools())?.name ?? `browser_${command}`
    const response = await fetch(`${apiBase}/call`, {
      method: 'POST',
      signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, arguments: parameters }),
    })
    if (!response.ok) throw new Error(`Browser transport returned HTTP ${response.status}`)
    const result = await response.json()
    // MCP delivers these text blocks directly to the model. Preserve their
    // line breaks for shell readers instead of adding a JSON-escaped envelope.
    const text =
      Array.isArray(result.content) && result.content.every((block) => block.type === 'text')
        ? result.content.map((block) => block.text).join('\n')
        : JSON.stringify(result) + '\n'
    // A failed call's text is its error, so a redirect or pipe of the
    // output does not swallow it.
    return result.isError
      ? { stdout: '', stderr: text, exitCode: 1 }
      : { stdout: text, stderr: '', exitCode: 0 }
  } catch (error) {
    return { stdout: '', stderr: `${error.message}\n`, exitCode: 1 }
  }
}
