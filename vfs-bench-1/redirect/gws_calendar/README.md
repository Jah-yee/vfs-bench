# Fake Google OAuth, for the calendar MCP server

`@gongrzhe/server-calendar-autoauth-mcp` refuses to start without an OAuth
keys file and, without saved credentials, opens a browser. Neither is
reachable here and neither is needed: [`calendar_hook.mjs`](calendar_hook.mjs)
sends every request to mirage's mock Google Workspace server, which accepts
any bearer token.

So these two files are the smallest thing that gets the server past its own
startup checks. `expiry_date` is the year 2100, which is what keeps
`google-auth-library` from trying to refresh the token against a token
endpoint nobody is running. Both arms of every calendar task share them.
