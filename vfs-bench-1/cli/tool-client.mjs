// Invoke an original tool handler through its service-specific CLI transport.
export async function runTool(service, argv, readStdin, apiBase, timeoutMs, prefix = '') {
  try {
    if (!apiBase) throw new Error(`${service} session is not running`)
    const [name, ...args] = argv
    const getTools = async () => {
      const response = await fetch(`${apiBase}/tools`, {
        signal: timeoutMs == null ? undefined : globalThis.AbortSignal.timeout(timeoutMs),
      })
      if (!response.ok) throw new Error(`${service}: HTTP ${response.status}`)
      return (await response.json()).tools.map((tool) => ({
        ...tool,
        name: tool.name.startsWith(prefix) ? tool.name.slice(prefix.length) : tool.name,
      }))
    }
    if (!name || name === '--help') {
      return {
        stdout:
          `${service} <command> ['<JSON arguments>' | -]\nUse ${service} <command> --help for the original argument schema.\n` +
          (await getTools()).map((tool) => `${tool.name}: ${tool.description}`).join('\n') +
          '\n',
        stderr: '',
        exitCode: 0,
      }
    }
    if (args.length === 1 && args[0] === '--help') {
      const tool = (await getTools()).find((tool) => tool.name === name)
      if (!tool) throw new Error(`Unknown ${service} command: ${name}`)
      return { stdout: JSON.stringify(tool, null, 2) + '\n', stderr: '', exitCode: 0 }
    }
    if (args.length > 1) throw new Error('Pass arguments as one JSON object')
    const parameters = args[0] === '-' ? await readStdin() : args[0] || '{}'
    const response = await fetch(`${apiBase}/call`, {
      signal: timeoutMs == null ? undefined : globalThis.AbortSignal.timeout(timeoutMs),
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: prefix + name, arguments: JSON.parse(parameters) }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.error || `${service}: HTTP ${response.status}`)
    const stdout = renderToolResult(result)
    return { stdout, stderr: '', exitCode: result.isError ? 1 : 0 }
  } catch (error) {
    return { stdout: '', stderr: `${error.message}\n`, exitCode: 1 }
  }
}

// Text is the MCP model-visible payload; non-text blocks retain their envelope.
export function renderToolResult(result) {
  return Array.isArray(result.content) && result.content.every((block) => block.type === 'text')
    ? result.content.map((block) => block.text).join('\n')
    : JSON.stringify(result) + '\n'
}
