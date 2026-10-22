import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'

const modules = {}
for (const name of ['apiClient', 'requestScope', 'generationRequest', 'referenceSettings', 'creationSettings', 'inpaintSettings', 'controlSettings', 'fluxSettings']) {
  let output = ts.transpileModule(await readFile(new URL('./src/' + name + '.ts', import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText
  for (const [dependency, url] of Object.entries(modules)) output = output.replaceAll("'./" + dependency + "'", JSON.stringify(url))
  modules[name] = 'data:text/javascript;base64,' + Buffer.from(output).toString('base64')
}
const { api, apiJson, apiText, apiResponse, ApiError } = await import(modules.apiClient)
const { createRequestScope } = await import(modules.requestScope)
const { submitOnce } = await import(modules.generationRequest)
const inpaint = await import(modules.inpaintSettings), control = await import(modules.controlSettings)
const originalFetch = globalThis.fetch
let attempts = []
function remote(reply) { attempts = []; globalThis.fetch = async (path, options) => { attempts.push({ path, options }); return typeof reply === 'function' ? reply(path, options) : reply } }
try {
  for (const [status, detail] of [[409, '修訂衝突'], [422, { message: '請保留原設定', job_id: 'original' }],
    [422, [{ loc: ['body', 'seed'], msg: 'Seed 必須是字串' }]], [500, null]]) {
    remote(new Response(JSON.stringify({ detail }), { status }))
    await assert.rejects(() => api('settings', 'PUT', { seed: '18446744073709551615' }), error => {
      assert(error instanceof ApiError); assert.equal(error.kind, 'http'); assert.equal(error.status, status)
      if (status === 422) assert.match(error.message, /原設定|seed/)
      return true
    })
    assert.equal(attempts.length, 1)
  }
  remote(new Response('<html>PRIVATE_UPSTREAM_TRACE</html>', { status: 502 }))
  await assert.rejects(() => api('jobs'), error => error.status === 502 && !error.message.includes('PRIVATE_') && !error.conclusive)
  remote(new Response('broken-json'))
  await assert.rejects(() => api('jobs'), error => error.kind === 'invalid-response')
  remote(() => { throw new TypeError('PRIVATE_NETWORK_DETAIL') })
  await assert.rejects(() => api('jobs'), error => error.kind === 'network' && !error.message.includes('PRIVATE_'))
  const cancelled = new AbortController(); cancelled.abort()
  remote(new Response('{}'))
  await assert.rejects(() => apiJson('jobs', { signal: cancelled.signal }), error => error.kind === 'aborted')
  assert.equal(attempts.length, 0)
  const scope = createRequestScope(), old = scope.begin(), fresh = scope.begin()
  assert.equal(old.signal.aborted, true); assert.equal(old.isCurrent(), false); assert.equal(fresh.isCurrent(), true)
  scope.cancel(); assert.equal(fresh.isCurrent(), false)
  const resumed = scope.begin(); scope.dispose(); assert.equal(resumed.isCurrent(), false); assert.throws(() => scope.begin())

  const raw = '{"seed":18446744073709551615,"nested":{"seed":9007199254740993}}\n'
  remote(new Response(raw)); assert.equal(await apiText('workflow'), raw)
  remote(new Response(raw)); assert.deepEqual(new Uint8Array(await (await apiResponse('workflow')).arrayBuffer()), new TextEncoder().encode(raw))
  remote(new Response('[]')); await api('settings', 'POST', false)
  assert.equal(attempts[0].options.body, 'false')

  const pending = Object.freeze({ request_id: 'frozen-id', seed: '18446744073709551615',
    loras: [{ name: 'second', enabled: true, strength_model: .5, strength_clip: 1 }, { name: 'first', enabled: true, strength_model: 1, strength_clip: .5 }] })
  const descriptors = [
    { path: '/api/generate', body: pending }, { path: '/api/flux/generate', body: pending },
    inpaint.inpaintSubmission({ ...pending }),
    inpaint.inpaintSubmission({ ...pending, [inpaint.inpaintPendingMarker]: inpaint.inpaintFeatherWorkflowId }),
    control.controlSubmission({ ...pending }),
    control.controlSubmission({ ...pending, [control.controlPendingMarker]: control.controlEdgeWorkflowId }),
  ]
  for (const descriptor of descriptors) {
    for (const reply of [() => { throw new TypeError('response lost') }, new Response('not-json'),
      new Response('null'), new Response('{}'), new Response('[]'), new Response('{"id":"another-id"}'),
      new Response('{"detail":{"message":"wrong job","job_id":"another-id"}}', { status: 503 }),
      new Response('{"detail":{"message":"wrong job","job_id":"another-id"}}', { status: 409 }),
      new Response('<html>proxy</html>', { status: 409 }), new Response('{}', { status: 503 })]) {
      remote(reply); let confirmed = false
      await assert.rejects(() => submitOnce(descriptor, () => { confirmed = true }))
      assert.equal(confirmed, false); assert.equal(attempts.length, 1)
      assert.equal(attempts[0].path, descriptor.path)
      const body = JSON.parse(attempts[0].options.body)
      assert.equal(body.request_id, 'frozen-id'); assert.equal(body.seed, pending.seed); assert.deepEqual(body.loras, pending.loras)
    }
    for (const [status, body] of [[200, { id: 'frozen-id' }], [409, { detail: 'failed' }], [503, { detail: { message: 'failed', job_id: 'frozen-id' } }]]) {
      remote(new Response(JSON.stringify(body), { status })); let confirmations = 0
      try { await submitOnce(descriptor, () => { confirmations++ }) } catch (error) { assert(error instanceof ApiError) }
      assert.equal(confirmations, 1); assert.equal(attempts.length, 1)
    }
  }
  assert.deepEqual(descriptors.slice(2).map(value => value.path), ['/api/inpaint/generate', '/api/inpaint-feather/generate', '/api/control/generate', '/api/control-edge/generate'])
  for (const action of ['refresh', 'cancel', 'stop']) {
    remote(() => { throw new TypeError('lost') })
    await assert.rejects(() => api('jobs/original/' + action, 'POST')); assert.equal(attempts.length, 1)
  }
  console.log('API errors, cancellation, untouched JSON bytes, six frozen submission descriptors and no-retry actions passed.')
} finally { globalThis.fetch = originalFetch }
