// A tool's command: its name less the CLI's prefix, with hyphens for
// underscores, so `read_pdf_pages` is `pdf-tools read-pdf-pages`.
export function commandName(tool, prefix = '') {
  return (tool.startsWith(prefix) ? tool.slice(prefix.length) : tool).replaceAll('_', '-')
}

// Invoke an original tool handler through its service-specific CLI transport.
export async function runTool(service, argv, apiBase, timeoutMs, prefix = '') {
  try {
    if (!apiBase) throw new Error(`${service} session is not running`)
    const [name, ...args] = argv
    const getTools = async () => {
      const response = await fetch(`${apiBase}/tools`, {
        signal: timeoutMs == null ? undefined : globalThis.AbortSignal.timeout(timeoutMs),
      })
      if (!response.ok) throw new Error(`${service}: HTTP ${response.status}`)
      return (await response.json()).tools
    }
    // The command typed, spelled with underscores or hyphens.
    const find = (tools) =>
      tools.find((tool) => commandName(tool.name, prefix) === commandName(name))
    if (!name || name === '--help') {
      return {
        stdout:
          `${service} <command> ['<JSON arguments>']\nUse ${service} <command> --help for the original argument schema.\n` +
          (await getTools())
            .map((tool) => `${commandName(tool.name, prefix)}: ${tool.description}`)
            .join('\n') +
          '\n',
        stderr: '',
        exitCode: 0,
      }
    }
    if (args.length === 1 && args[0] === '--help') {
      const tool = find(await getTools())
      if (!tool) throw new Error(`Unknown ${service} command: ${name}`)
      return {
        stdout: JSON.stringify({ ...tool, name: commandName(tool.name, prefix) }, null, 2) + '\n',
        stderr: '',
        exitCode: 0,
      }
    }
    if (args.length > 1) throw new Error('Pass arguments as one JSON object')
    const parameters = parseArguments(args[0] || '{}')
    // A command no tool answers to goes to the server as typed, which
    // answers it as upstream's does.
    const tool = find(await getTools())
    const response = await fetch(`${apiBase}/call`, {
      signal: timeoutMs == null ? undefined : globalThis.AbortSignal.timeout(timeoutMs),
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: tool ? tool.name : prefix + name, arguments: parameters }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.error || `${service}: HTTP ${response.status}`)
    const text = renderToolResult(result)
    // A failed call's text is its error, so it goes where a command's errors
    // go: a redirect or pipe of the output does not swallow it.
    return result.isError
      ? { stdout: '', stderr: text, exitCode: 1 }
      : { stdout: text, stderr: '', exitCode: 0 }
  } catch (error) {
    return { stdout: '', stderr: `${error.message}\n`, exitCode: 1 }
  }
}

// The JSON arguments as the shell passes them. A string typed over several
// lines carries raw line breaks, which JSON.parse refuses and Python's
// json.loads(strict=False) accepts, so they are escaped first.
export function parseArguments(text) {
  return JSON.parse(
    text.replace(/"(?:[^"\\]|\\[^])*"/g, (string) =>
      string.replace(/\\[^]|[\0-\x1f]/g, (match) =>
        match.length > 1 ? match : `\\u${match.charCodeAt(0).toString(16).padStart(4, '0')}`,
      ),
    ),
  )
}

// Text is the MCP model-visible payload; non-text blocks retain their envelope.
export function renderToolResult(result) {
  return Array.isArray(result.content) && result.content.every((block) => block.type === 'text')
    ? result.content.map((block) => block.text).join('\n')
    : JSON.stringify(result) + '\n'
}
