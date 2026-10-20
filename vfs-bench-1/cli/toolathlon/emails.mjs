// The pinned emails-mcp handlers under their original tool names and schemas.
import { toolCommand } from './tool.mjs'

export const EMAILS = toolCommand('emails', '', {
  // The one rest-argument spec covers both reads and writes. Declaring the
  // combined surface writable is conservative and makes Mirage invalidate
  // account-backed mount caches after calls that can mutate IMAP state.
  write: true,
})
