import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { compileScript, parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import { createRenderer, h, KeepAlive, nextTick, ref, reactive } from 'vue'

// Exercise actual SFC setup/lifecycle code with Vue's renderer. Children are
// absent so these checks never create a generation panel or a GPU request.
const cache = new Map(), stub = 'data:text/javascript;base64,' + Buffer.from('export default {render(){return null}}').toString('base64')
async function moduleUrl(name) {
  if (cache.has(name)) return cache.get(name)
  const url = new URL('./src/' + name, import.meta.url), filename = fileURLToPath(url)
  let source = await readFile(url, 'utf8')
  if (name.endsWith('.vue')) source = compileScript(parse(source, { filename }).descriptor, { id: name }).content
  let code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText
  const dependencies = [...code.matchAll(/from\s+['"]([^'"]+)['"]/g)].map(match => match[1])
  for (const dependency of new Set(dependencies)) {
    const target = dependency === 'vue' ? import.meta.resolve('vue') : dependency.endsWith('.vue') ? stub
      : dependency.startsWith('./') ? await moduleUrl(dependency.slice(2) + (dependency.endsWith('.ts') ? '' : '.ts')) : null
    if (target) code = code.replaceAll("'" + dependency + "'", JSON.stringify(target)).replaceAll('"' + dependency + '"', JSON.stringify(target))
  }
  const result = 'data:text/javascript;base64,' + Buffer.from(code).toString('base64')
  cache.set(name, result)
  return result
}

const renderer = createRenderer({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
  insert() {}, remove() {}, setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null, patchProp() {},
})
const unloadListeners = new Set()
globalThis.window = {
  addEventListener(type, handler) { if (type === 'beforeunload') unloadListeners.add(handler) },
  removeEventListener(type, handler) { if (type === 'beforeunload') unloadListeners.delete(handler) },
  setTimeout, clearTimeout, setInterval, clearInterval,
}
globalThis.document = { visibilityState: 'visible', addEventListener() {}, removeEventListener() {} }
const storage = new Map()
globalThis.localStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) }
const originalFetch = globalThis.fetch
const engine = 'http://engine-current:8188'
const response = payload => new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } })
function payload(path) {
  if (path === '/api/settings') return { comfy_url: engine }
  if (path === '/api/models') return { engine_url: engine, models: [] }
  if (path === '/api/controlnets') return { engine_url: engine, controlnets: [] }
  if (path === '/api/flux/components') return { engine_url: engine, groups: {} }
  if (path === '/api/flux/workflow') return { id: 'flux1-schnell-text2image-v1', cfg: 1, gpu_verified: false }
  if (path === '/api/engine/capabilities') return { engine_url: engine, engine_matches: true, available: false, stale: false, sampler_names: [], schedulers: [], bounds: {} }
  return []
}
async function settle() { for (let i = 0; i < 12; i++) { await nextTick(); await new Promise(resolve => setImmediate(resolve)) } }
try {
  for (const name of ['CreationStudio.vue', 'FluxStudio.vue', 'InpaintStudio.vue', 'ControlStudio.vue']) {
    let delayed = false, waiting = []
    const target = name === 'FluxStudio.vue' ? '/api/flux/components' : '/api/models'
    globalThis.fetch = async (path, options) => {
      assert.equal(options.method === 'POST' && String(path).endsWith('/generate'), false)
      if (delayed && path === target) return new Promise(resolve => waiting.push({ resolve, signal: options.signal }))
      return response(payload(path))
    }
    const component = (await import(await moduleUrl(name))).default
    component.render = () => null
    let ui
    const visible = ref(true), app = renderer.createApp({ render: () => h(KeepAlive, null, { default: () => visible.value
      ? h(component, { ref: value => { if (value) ui = value.$.setupState } }) : h({ render: () => null }) }) })
    app.mount({}); await settle()
    assert(ui, name)
    assert.equal(unloadListeners.size, 0, name + ': pristine form has no unload handler')
    if ('savingDraft' in ui) {
      ui.savingDraft = true; assert.equal(unloadListeners.size, 1)
      ui.savingDraft = false; assert.equal(unloadListeners.size, 0)
    }
    if ('maskDirty' in ui) {
      ui.maskDirty = true; assert.equal(unloadListeners.size, 1)
      ui.maskDirty = false; assert.equal(unloadListeners.size, 0)
    }
    ui.form.prompt = 'unsaved prompt'; ui.form.seed = '18446744073709551615'
    if ('loras' in ui.form) ui.form.loras = [{ name: 'ordered', enabled: true, strength_model: .5, strength_clip: 1 }]
    const retained = JSON.stringify(ui.form)
    assert.equal(unloadListeners.size, 1, name + ': edits protect unload')
    let prevented = false
    const event = { preventDefault() { prevented = true }, returnValue: undefined }
    for (const handler of unloadListeners) handler(event)
    assert.equal(prevented, true); assert.equal(event.returnValue, '')
    delayed = true
    const older = name === 'CreationStudio.vue' ? ui.refresh() : ui.load()
    await settle(); assert.equal(waiting.length, 1, name)
    visible.value = false; await settle()
    assert.equal(unloadListeners.size, 1, name + ': cached form protects whole page')
    assert.equal(waiting[0].signal.aborted, true, name)
    delayed = false; visible.value = true; await settle()
    waiting[0].resolve(response({ ...payload(target), engine_url: 'http://obsolete-engine' }))
    await older; await settle()
    assert.equal((name === 'CreationStudio.vue' ? ui.models : ui.catalog).engine_url, engine, name)
    assert.equal(JSON.stringify(ui.form), retained, name)
    assert.equal(ui.error, '', name)
    // A late reply after unmount also stays cancelled without a state write.
    delayed = true; waiting = []
    const leaving = name === 'CreationStudio.vue' ? ui.refresh() : ui.load()
    await settle()
    const beforeUnmount = name === 'CreationStudio.vue' ? ui.models : ui.catalog
    app.unmount()
    assert.equal(unloadListeners.size, 0, name + ': no leaked unload handlers')
    assert.equal(waiting[0].signal.aborted, true, name)
    waiting[0].resolve(response({ ...payload(target), engine_url: 'http://obsolete-engine' }))
    await leaving; await settle()
    assert.equal(name === 'CreationStudio.vue' ? ui.models : ui.catalog, beforeUnmount, name)
    console.log(name + ': deactivation, reactivation, ignored abort, unmount and unsaved parameters passed.')
  }
  const { newCreation } = await import(await moduleUrl('creationSettings.ts'))
  const { newFlux } = await import(await moduleUrl('fluxSettings.ts'))
  const inpaint = await import(await moduleUrl('inpaintSettings.ts')), control = await import(await moduleUrl('controlSettings.ts'))
  const component = (await import(await moduleUrl('GenerationPanel.vue'))).default
  component.render = () => null
  for (const [workflow, form, key, path] of [
    [undefined, newCreation(), 'atelier-pending-submission', '/api/generate'],
    ['flux', newFlux(engine), 'atelier-pending-flux-submission', '/api/flux/generate'],
    ['inpaint', inpaint.newInpaint(), 'atelier-pending-inpaint-submission', '/api/inpaint/generate'],
    ['control', control.newControl(), 'atelier-pending-control-submission', '/api/control/generate'],
  ]) {
    storage.clear()
    const frozen = { ...form, request_id: 'original-uuid', seed: '18446744073709551615', prompt: 'original prompt' }
    storage.set(key, JSON.stringify(frozen))
    const requests = []
    let lost = true, ui
    globalThis.fetch = async (url, options) => {
      if (String(url).startsWith('/api/library/jobs?')) return response({items:[],next_cursor:null})
      requests.push({ url, body: JSON.parse(options.body) })
      if (lost) throw new TypeError('lost response')
      return response({ id: frozen.request_id, status: 'queued' })
    }
    const editable = reactive(form)
    const app = renderer.createApp({ render: () => h(component, { form: editable, workflow, ref: value => { if (value) ui = value.$.setupState } }) })
    app.mount({}); await settle()
    await ui.generate(); await settle()
    assert.equal(requests.length, 1); assert.equal(ui.pending.request_id, 'original-uuid')
    assert.equal(JSON.parse(storage.get(key)).seed, frozen.seed)
    editable.seed = '123'; editable.prompt = 'changed after unknown response'; lost = false
    await ui.generate(); await settle()
    assert.equal(requests.length, 2)
    assert.equal(requests[1].url, path); assert.deepEqual(requests[1].body, requests[0].body)
    assert.equal(requests[1].body.seed, frozen.seed); assert.equal(ui.pending, null); assert.equal(storage.has(key), false)
    app.unmount()
    console.log((workflow || 'checkpoint') + ': actual GenerationPanel restores original UUID/body/endpoint after lost response.')
  }
  const gallery = (await import(await moduleUrl('ArtworkLibrary.vue'))).default
  gallery.render = () => null
  let artworkUi, writes = 0
  globalThis.fetch = async (url, options) => {
    if (options.method === 'PATCH') { writes++; return new Response(JSON.stringify({ detail: '作品修訂衝突，筆記保留' }), { status: 409 }) }
    if (String(url).startsWith('/api/library/')) return response({items:[],total:0,offset:0,models:[],missing_ids:[],next_cursor:null,previous_cursor:null})
    return response([])
  }
  const galleryApp = renderer.createApp({ render: () => h(gallery, { ref: value => { if (value) artworkUi = value.$.setupState } }) })
  galleryApp.mount({}); await settle()
  const item = { parameters: {}, id: 'artwork', notes: 'saved', revision: 2, ratings: { prompt_adherence: null, character_consistency: null, visual_style: null, composition: null } }
  await artworkUi.open(item)
  artworkUi.notesDraft = 'unsaved note after conflict'
  await artworkUi.organize(item, { notes: artworkUi.notesDraft }, 'saved')
  assert.equal(writes, 1); assert.equal(artworkUi.notesDraft, 'unsaved note after conflict')
  assert.equal(artworkUi.selected.revision, 2); assert.match(artworkUi.organizationError, /衝突/)
  galleryApp.unmount()
  console.log('ArtworkLibrary: 409 preserves actual unsaved notes, ratings and revision without retry.')
} finally { globalThis.fetch = originalFetch }
