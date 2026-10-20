// Use Mirage's API mock with captured benchmark observations. Its synthetic
// two-item page cap is for integration stress tests, not the public API.
import { startWandb } from '../../submodule/mirage/integ/server/wandb/fake.ts'
import { schema } from '../../submodule/mirage/integ/server/wandb/schema.ts'
import { loadFixture } from '../../submodule/mirage/integ/server/wandb/store.ts'
import { startFiles } from './wandb_files.mjs'
import {
  checkArgv,
  parseFixture,
  parseFixtureRoot,
  parsePort,
} from '../../submodule/mirage/integ/server/kit/typescript/port.ts'

checkArgv()
const fixture = loadFixture(parseFixture(), parseFixtureRoot())
const runs = Object.values(fixture.entities).flatMap((projects) => Object.values(projects).flat())
const byId = new Map(runs.map((run) => [run.id, run]))
schema.getType('Project').getFields().id.resolve = (source) =>
  fixture.projects[`${source.entityName}/${source.name}`].id
schema.getType('Project').getFields().isBenchmark.resolve = (source) =>
  fixture.projects[`${source.entityName}/${source.name}`].isBenchmark

function page(resolve, args) {
  const first = args.first ?? 50
  let result = resolve(args)
  const edges = [...result.edges]
  const initial = result.pageInfo
  while (edges.length < first && result.pageInfo.hasNextPage) {
    result = resolve({ ...args, after: result.pageInfo.endCursor, first: first - edges.length })
    edges.push(...result.edges)
  }
  return {
    ...result,
    edges,
    pageInfo: {
      ...result.pageInfo,
      startCursor: initial.startCursor,
      hasPreviousPage: initial.hasPreviousPage,
    },
  }
}

for (const [type, field] of [
  ['Query', 'models'],
  ['Project', 'runs'],
  ['Run', 'files'],
]) {
  schema.getType(type).getFields()[field].resolve = (source, args) => {
    if (field === 'runs') {
      args = { ...args, order: (args.order || '-created_at').replace(/createdAt$/, 'created_at') }
    }
    return page(source[field], args)
  }
}
// Preserve source counters even when W&B's public file catalog omits an item.
for (const field of ['projectId', 'fileCount', 'historyLineCount']) {
  schema.getType('Run').getFields()[field].resolve = (source) => byId.get(source.id)[field]
}
schema.getType('Run').getFields().history.resolve = (source, args) => {
  const run = byId.get(source.id)
  const supplied = Object.fromEntries(Object.entries(args).filter(([, value]) => value != null))
  const capture = run.historySamples?.find(
    (item) => argumentKey(item.args) === argumentKey(supplied),
  )
  if (!capture && args.maxStep - args.minStep === 1) {
    throw new Error('one-step history requires a captured W&B response')
  }
  return capture ? capture.rows : source.history(args)
}

function argumentKey(args) {
  return JSON.stringify(Object.fromEntries(Object.entries(args).sort()))
}

function specKey(spec) {
  // Source captures verify that these legacy options have no effect.
  const args = Object.fromEntries(
    Object.entries(spec).filter(([key]) => !['x_axis', 'start', 'end', 'stride'].includes(key)),
  )
  return argumentKey({ ...args, keys: [...(args.keys ?? [])].sort() })
}
schema.getType('Run').getFields().sampledHistory.resolve = (source, { specs }) => {
  const run = byId.get(source.id)
  return specs.map((raw) => {
    const spec = JSON.parse(raw)
    // These defaults and null exclusion were probed on the source API.
    if (!spec.samples || !spec.keys?.length) return []
    const capture = run.selectedHistorySamples?.find((item) => specKey(item.spec) === specKey(spec))
    if (capture) return capture.rows
    for (const key of Object.keys(spec)) {
      if (
        !['minStep', 'maxStep', 'samples', 'keys', 'x_axis', 'start', 'end', 'stride'].includes(key)
      ) {
        throw new Error('unsupported sampled history option')
      }
    }
    const rows = run.history.filter(
      (row) =>
        row._step >= (spec.minStep ?? 0) &&
        row._step <= (spec.maxStep ?? Infinity) &&
        spec.keys.every((key) => row[key] !== undefined && row[key] !== null),
    )
    if (rows.length > spec.samples) throw new Error('downsampling requires a captured W&B response')
    return rows.map((row) => Object.fromEntries(spec.keys.map((key) => [key, row[key]])))
  })
}

for (const field of ['id', 'sizeBytes', 'md5']) {
  schema.getType('File').getFields()[field].resolve = (source) => {
    const [entity, project, runId, ...parts] = new URL(source.directUrl).pathname
      .slice('/storage/'.length)
      .split('/')
      .map(decodeURIComponent)
    const file = fixture.entities[entity][project].find((run) => run.name === runId).files[
      parts.join('/')
    ]
    return file[{ id: 'sourceId', sizeBytes: 'sourceSizeBytes', md5: 'sourceMd5' }[field]]
  }
}

const remote = runs.some((run) => Object.values(run.files).some((file) => file.remote))
const server = await startWandb(remote ? 0 : parsePort(), parseFixture(), parseFixtureRoot())
const files = remote ? await startFiles(server.base, fixture, parsePort()) : server
console.log(`WANDB_BASE_URL=${files.base}`)
