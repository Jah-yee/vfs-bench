// Preserve the original fetch handlers; both arms read one public HTTP cache.
const nativeFetch = globalThis.fetch
globalThis.fetch = async (url, options = {}) => {
  const response = await nativeFetch(`${process.env.WEB_API_URL}/http`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: String(url), headers: options.headers ?? {} }),
    signal: options.signal,
  })
  const result = await response.json()
  if (!response.ok) throw new Error(result.error)
  return new Response(
    [204, 205, 304].includes(result.status) ? null : Buffer.from(result.body, 'base64'),
    { status: result.status, headers: result.headers },
  )
}
