// Redirect Google API requests without editing original Forms tool handlers.
import { createRequire } from 'node:module'
const require = createRequire(new URL('../../vendor/forms-mcp/src/package.json', import.meta.url))
const { google } = require('googleapis')
const base = process.env.GWS_MOCK_URL?.replace(/\/$/, '')
if (!base) throw new Error('GWS_MOCK_URL is not set')
const original = google.forms

google.forms = function (options) {
  options.auth.setCredentials({ access_token: 'gws-integ-token' })
  const api = original.call(this, options)
  for (const [resource, names] of [
    [api.forms, ['create', 'get', 'batchUpdate']],
    [api.forms.responses, ['list', 'get']],
  ]) {
    for (const name of names) {
      const method = resource[name]
      resource[name] = function (params, options, callback) {
        if (typeof options === 'function')
          return method.call(this, params, { rootUrl: base + '/' }, options)
        return method.call(this, params, { ...options, rootUrl: base + '/' }, callback)
      }
    }
  }
  return api
}
