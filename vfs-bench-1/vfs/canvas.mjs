import { ServiceVFS } from './service_api.mjs'
import { enoent } from '../submodule/mirage/typescript/packages/core/dist/errors/fs.js'

export class CanvasVFS extends ServiceVFS {
  constructor(config) {
    super({ ...config, kind: 'canvas' })
  }
  endpoint(path) {
    if (path === 'profile') return 'users/self/profile'
    if (path === 'files') return 'users/self/files'
    if (/^courses\/\d+\/assignments\/\d+\/submission$/.test(path))
      return path.replace(/submission$/, 'submissions/self')
    if (/^courses\/\d+\/announcements(\/\d+)?$/.test(path))
      return (
        path.replace('announcements', 'discussion_topics') +
        (/announcements$/.test(path) ? '?only_announcements=true' : '')
      )
    const allowed = [
      /^courses\/\d+\/quizzes\/\d+\/submissions(\/\d+)?$/,
      /^quiz_submissions\/\d+\/questions(\/\d+)?$/,
      /^users\/self\/files(\/\d+)?$/,
      /^files\/\d+$/,
      /^courses(\/\d+)?$/,
      /^courses\/\d+\/(assignments|quizzes|users|enrollments)(\/\d+)?$/,
      /^courses\/\d+\/quizzes\/\d+\/questions(\/\d+)?$/,
      /^courses\/\d+\/assignments\/\d+\/submissions(\/(self|\d+))?$/,
      /^accounts\/\d+(\/(users|courses)(\/\d+)?)?$/,
      /^conversations(\/\d+)?$/,
    ]
    if (!allowed.some((pattern) => pattern.test(path))) throw enoent(path)
    return path
  }
  async accessible(path, names) {
    // Synthetic branches must exist for the current identity. Teachers may
    // read a course without account access or a personal assignment submission.
    const visible = []
    for (const name of names) {
      const child = [path, name.replace(/\.json$/, '')].filter(Boolean).join('/')
      try {
        await this.client.request('GET', this.endpoint(child), undefined, { per_page: 1 })
        visible.push(name)
      } catch (error) {
        if (![401, 403, 404].includes(error.status)) throw error
      }
    }
    return visible
  }
  async object(path) {
    // These Canvas collections have no matching single-object GET route.
    // Preserve the complete collection row rather than substituting a profile.
    const question = path.match(/^(quiz_submissions\/\d+\/questions)\/(\d+)$/)
    if (question) {
      const rows = await this.client.list(question[1])
      const found = rows.find((item) => String(item.id) === question[2])
      if (!found) throw enoent(path)
      return found
    }
    const row = path.match(/^((?:accounts|courses)\/\d+\/(?:users|enrollments))\/(\d+)$/)
    if (row) {
      const objects = await this.client.list(row[1])
      const found = objects.find((item) => String(item.id) === row[2])
      if (!found) throw enoent(path)
      return found
    }
    return super.object(path)
  }
  async listing(path) {
    if (!path) {
      // Fail visibly for invalid credentials instead of returning an empty mount.
      await this.object('profile')
      const names = await this.accessible('', ['courses', 'conversations', 'files'])
      return [
        'profile.json',
        ...names,
        ...((await this.listing('accounts')).length ? ['accounts'] : []),
      ]
    }
    if (path === 'files')
      return (await this.client.list('users/self/files')).map((row) => `${row.id}.json`)
    if (path === 'accounts') {
      const courses = await this.client.list('courses')
      return this.accessible('accounts', [
        ...new Set(
          courses
            .filter((course) => course.account_id != null)
            .map((course) => String(course.account_id)),
        ),
      ])
    }
    if (/^accounts\/\d+$/.test(path)) {
      await this.client.request('GET', path)
      return this.accessible(path, ['users', 'courses'])
    }
    if (/^courses\/\d+$/.test(path)) {
      await this.client.request('GET', path)
      return this.accessible(path, [
        'assignments',
        'quizzes',
        'users',
        'enrollments',
        'announcements',
      ])
    }
    if (/^courses\/\d+\/assignments\/\d+$/.test(path)) {
      await this.client.request('GET', path)
      return this.accessible(path, ['submission.json', 'submissions'])
    }
    if (/^courses\/\d+\/quizzes\/\d+$/.test(path)) {
      await this.client.request('GET', path)
      return this.accessible(path, ['questions', 'submissions'])
    }
    const rows = await this.client.list(this.endpoint(path))
    if (/^courses\/\d+\/assignments\/\d+\/submissions$/.test(path))
      return rows.map((row) => `${row.user_id}.json`)
    const directory = path === 'courses' || /^courses\/\d+\/(assignments|quizzes)$/.test(path)
    return rows.flatMap((row) => [`${row.id}.json`, ...(directory ? [String(row.id)] : [])])
  }
}
