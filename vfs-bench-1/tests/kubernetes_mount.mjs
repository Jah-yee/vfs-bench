import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createRequire } from 'node:module'
import { Workspace } from '../submodule/mirage/typescript/packages/node/dist/workspace.js'
import { KubernetesVFS } from '../vfs/kubernetes.mjs'

const require = createRequire(
  new URL('../submodule/mirage/typescript/packages/node/package.json', import.meta.url),
)
const yaml = require('yaml')
const source = execFileSync(
  'git',
  [
    '-C',
    'submodule/Toolathlon',
    'show',
    'HEAD:tasks/finalpool/k8s-deployment-cleanup/k8s_resources/k8s_deployment_cleanup.yaml',
  ],
  { encoding: 'utf8' },
)
const deployments = yaml
  .parseAllDocuments(source)
  .map((d) => d.toJSON())
  .filter((d) => d?.kind === 'Deployment')
const namespaces = [...new Set(deployments.map((d) => d.metadata.namespace))]
const scratch = mkdtempSync(join(tmpdir(), 'kubernetes-mount-'))
const kubeconfig = join(scratch, 'config.json')
writeFileSync(
  kubeconfig,
  JSON.stringify({
    'current-context': 'test',
    contexts: [{ name: 'test', context: { cluster: 'test', user: 'test' } }],
    clusters: [
      { name: 'test', cluster: { server: 'https://127.0.0.1', 'certificate-authority-data': '' } },
    ],
    users: [{ name: 'test', user: { 'client-certificate-data': '', 'client-key-data': '' } }],
  }),
)
try {
  for (const mount of ['/k8s', '/nested/cluster']) {
    const vfs = new KubernetesVFS({ kubeconfig })
    const documents = new Map()
    documents.set('/api/v1/namespaces', {
      items: namespaces.map((name) => ({ metadata: { name } })),
    })
    for (const name of namespaces) {
      documents.set(`/api/v1/namespaces/${name}`, { metadata: { name } })
      documents.set(`/apis/apps/v1/namespaces/${name}/deployments`, {
        items: deployments.filter((d) => d.metadata.namespace === name),
      })
    }
    for (const deployment of deployments) {
      const { name, namespace } = deployment.metadata
      documents.set(`/apis/apps/v1/namespaces/${namespace}/deployments/${name}`, deployment)
    }
    vfs.client.resources = async () =>
      new Map([['deployments', { name: 'deployments', base: '/apis/apps/v1', namespaced: true }]])
    // A namespace the credential may not read and a deployment it may not see.
    const refused = new Map([
      ['/api/v1/namespaces/locked', 403],
      [`/apis/apps/v1/namespaces/${namespaces[0]}/deployments/sealed`, 401],
    ])
    vfs.client.request = async (path) => {
      if (refused.has(path)) {
        const status = refused.get(path)
        throw Object.assign(new Error(`Kubernetes ${status}: ${path}`), { status })
      }
      if (!documents.has(path))
        throw Object.assign(new Error(`Kubernetes 404: ${path}`), { status: 404 })
      return structuredClone(documents.get(path))
    }
    const ws = new Workspace({ [mount]: vfs })
    async function run(command) {
      const result = await ws.shell(command)
      assert.equal(result.exitCode, 0, new TextDecoder().decode(result.stderr ?? new Uint8Array()))
      return new TextDecoder().decode(result.stdout)
    }
    try {
      assert.deepEqual(
        (await run(`ls ${mount}/namespaces`)).trim().split('\n'),
        namespaces.toSorted(),
      )
      const target = deployments[0]
      const { name, namespace } = target.metadata
      const base = `${mount}/namespaces/${namespace}/deployments`
      assert.ok((await run(`ls ${base}`)).includes(`${name}.json`))
      const file = `${base}/${name}.json`
      assert.deepEqual(JSON.parse(await run(`cat ${file}`)), target)
      assert.deepEqual(JSON.parse(await run(`cat ${base}/*.json`)), target)
      const previous = target.spec.replicas
      target.spec.replicas = 0
      assert.equal(JSON.parse(await run(`cat ${file}`)).spec.replicas, 0)
      target.spec.replicas = previous
      assert.notEqual((await ws.shell(`echo invalid > ${file}`)).exitCode, 0)
      assert.notEqual((await ws.shell(`ls ${mount}/namespaces/missing`)).exitCode, 0)
      assert.notEqual((await ws.shell(`cat ${base}/missing.json`)).exitCode, 0)
      // A missing path is ENOENT, so a test of it is false rather than an
      // error that ends the command line.
      const exists = async (p) => (await run(`[ -e ${p} ] && echo yes || echo no`)).trim()
      assert.equal(await exists(file), 'yes')
      assert.equal(await exists(`${base}/missing.json`), 'no')
      assert.equal(await exists(`${mount}/namespaces/missing`), 'no')
      assert.equal(await exists(`${mount}/namespaces/${namespace}/nosuchtype`), 'no')
      assert.equal(await exists(`${mount}/bogus`), 'no')
      assert.match(
        new TextDecoder().decode((await ws.shell(`cat ${base}/missing.json`)).stderr),
        /No such file or directory/,
      )
      // A refused credential is EACCES, for a listing and for a read.
      for (const command of [
        `ls ${mount}/namespaces/locked`,
        `cat ${mount}/namespaces/${namespaces[0]}/deployments/sealed.json`,
      ]) {
        const result = await ws.shell(command)
        assert.notEqual(result.exitCode, 0, command)
        assert.match(new TextDecoder().decode(result.stderr), /Permission denied/, command)
      }
    } finally {
      await ws.close()
    }
  }
} finally {
  rmSync(scratch, { recursive: true, force: true })
}
console.log(
  'Kubernetes mount: nested paths, globs, fresh reads, read-only behavior and missing paths PASS',
)
