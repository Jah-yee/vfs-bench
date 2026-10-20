// The original tools' names, schemas and responses; no general Google API CLI.
import { toolCommand } from './tool.mjs'

export const CALENDAR = toolCommand('google-calendar', '', { write: true })
export const SHEETS = toolCommand('google-sheet', '', { write: true })
