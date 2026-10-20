// Track owned subprocess groups so cancelling a workspace can await cleanup.
import { writeFileSync, unlinkSync } from 'node:fs'
import { join } from 'node:path'

export function track(child, directory, background = false) {
  if (!directory || !child.pid) return
  const file = join(directory, `${child.pid}.json`)
  writeFileSync(file, JSON.stringify({ pid: child.pid, parent: process.pid, background }))
  child.once('close', () => {
    try {
      unlinkSync(file)
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
    }
  })
}
