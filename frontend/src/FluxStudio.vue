<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import GenerationPanel from './GenerationPanel.vue'
import ComponentSnapshot from './ComponentSnapshot.vue'
import RuntimeSnapshot from './RuntimeSnapshot.vue'
import type { RuntimeMetadata } from './runtimeMetadata'
import { fluxProblem, fluxRoles, fluxWorkflowId, newFlux, type FluxCatalog, type FluxForm, type ComponentSnapshot as ComponentMetadata } from './fluxSettings'

type Draft = FluxForm & { id: string; revision: number; updated_at: string }
type Restoration = { settings: FluxForm; component_metadata: ComponentMetadata[] | null; runtime_metadata?: RuntimeMetadata | null; engine_matches: boolean; warnings: string[] }
const props = defineProps<{ restoreRequest?: { artworkId: string; token: number } | null }>()
const emit = defineEmits<{ models: []; gallery: [id: string] }>()
const form = reactive(newFlux()), records = ref<Draft[]>([]), catalog = ref<FluxCatalog | null>(null)
const currentEngine = ref(''), id = ref<string | null>(null), revision = ref<number | null>(null)
const busy = ref(false), loading = ref(false), error = ref(''), message = ref('')
const saved = ref(JSON.stringify(form)), origin = ref<Restoration | null>(null)
const previewJson = ref('')
const pending = ref<Draft | Restoration | 'new' | null>(null)
const dirty = computed(() => saved.value !== JSON.stringify(form))
const problem = computed(() => fluxProblem(form))
const block = computed(() => problem.value || (currentEngine.value !== form.engine_url ? '原引擎與目前設定不同；請確認設定或建立目前引擎的新草稿。' : ''))
let ticket = 0, abort: AbortController | null = null, mounted = false, restoredToken = 0

async function api(path: string, options?: RequestInit) {
  const response = await fetch('/api/' + path, options)
  const value = await response.json()
  if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : value.detail?.message || '請檢查輸入或服務狀態。')
  return value
}
function model(role: typeof fluxRoles[number]) {
  return catalog.value?.engine_url === form.engine_url ? catalog.value.groups[role.category]?.find(item => item.name === form[role.key]) : undefined
}
function choices(category: string) {
  return catalog.value?.engine_url === form.engine_url ? catalog.value.groups[category]?.filter(item => item.listed) || [] : []
}
async function load(sync = false) {
  const token = ++ticket
  abort?.abort(); const controller = new AbortController(); abort = controller
  loading.value = true; error.value = ''
  try {
    const settings = await api('settings', { signal: controller.signal })
    const [inventory, drafts, description] = await Promise.all([
      api('flux/components' + (sync ? '/sync' : ''), sync ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ engine_url: settings.comfy_url }), signal: controller.signal } : { signal: controller.signal }),
      api('flux/drafts', { signal: controller.signal }), api('flux/workflow', { signal: controller.signal }),
    ])
    const latest = await api('settings', { signal: controller.signal })
    if (token !== ticket) return
    currentEngine.value = latest.comfy_url
    if (description.id !== fluxWorkflowId || description.cfg !== 1 || description.gpu_verified !== false) throw new Error('FLUX 流程描述不相容；請更新平台。')
    records.value = drafts
    if (latest.comfy_url !== settings.comfy_url || inventory.engine_url !== latest.comfy_url) {
      catalog.value = null; throw new Error('查詢期間引擎設定已變更，請重新整理。')
    }
    catalog.value = inventory
    if (!form.engine_url) {
      form.engine_url = currentEngine.value
      saved.value = JSON.stringify({ ...JSON.parse(saved.value), engine_url: currentEngine.value })
    }
    if (inventory.sync_error) error.value = inventory.sync_error
  } catch (e) {
    if (token === ticket && !(e instanceof DOMException && e.name === 'AbortError')) error.value = e instanceof Error ? e.message : '讀取失敗'
  } finally { if (token === ticket) loading.value = false }
}
function apply(value: Draft | Restoration | 'new') {
  if (value === 'new') {
    Object.assign(form, newFlux(currentEngine.value)); id.value = null; revision.value = null; origin.value = null
  } else if ('settings' in value) {
    Object.assign(form, value.settings); id.value = null; revision.value = null; origin.value = value
  } else {
    const settings = Object.fromEntries(Object.keys(newFlux()).map(key => [key, value[key as keyof FluxForm]]))
    Object.assign(form, settings); id.value = value.id; revision.value = value.revision; origin.value = null
  }
  saved.value = JSON.stringify(form); pending.value = null; message.value = '已載入設定；尚未提交生成。'
}
function choose(value: Draft | Restoration | 'new') { if (dirty.value) pending.value = value; else apply(value) }
async function save(asNew = false) {
  if (busy.value || problem.value) return
  busy.value = true; error.value = ''; message.value = ''
  try {
    const existing = !asNew && id.value
    const value = await api('flux/drafts' + (existing ? '/' + id.value : ''), {
      method: existing ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...form, ...(existing ? { revision: revision.value } : {}) }),
    }) as Draft
    id.value = value.id; revision.value = value.revision; saved.value = JSON.stringify(form)
    records.value = [value, ...records.value.filter(item => item.id !== value.id)]
    message.value = 'FLUX 草稿已保存；未啟動 GPU 任務。'
  } catch (e) { error.value = e instanceof Error ? e.message : '保存失敗' }
  finally { busy.value = false }
}
async function restore(path: string) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { choose(await api(path) as Restoration) }
  catch (e) { error.value = e instanceof Error ? e.message : '載入失敗' }
  finally { busy.value = false }
}
async function downloadPreview() {
  if (busy.value || problem.value) return
  busy.value = true; error.value = ''
  try {
    const value = await api('flux/workflow', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) })
    if (typeof value.workflow_json !== 'string') throw new Error('JSON 匯出格式不相容；未使用瀏覽器轉換數值。')
    previewJson.value = value.workflow_json
    const url = URL.createObjectURL(new Blob([value.workflow_json], { type: 'application/json' }))
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'model-atelier-flux-workflow.json'; anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    message.value = '完整 JSON 已匯出；未建立任務。'
  } catch (e) { error.value = e instanceof Error ? e.message : '匯出失敗' }
  finally { busy.value = false }
}
watch(() => props.restoreRequest, value => {
  if (!value || value.token === restoredToken) return
  restoredToken = value.token; void restore('flux/artworks/' + value.artworkId + '/creation-settings')
}, { immediate: true })
onMounted(async () => { await load(); mounted = true })
onActivated(() => { if (mounted) void load() })
function cancelLoad() { ++ticket; abort?.abort(); loading.value = false }
onDeactivated(cancelLoad); onBeforeUnmount(cancelLoad)
</script>

<template>
  <section aria-label="FLUX 創作工作台">
    <div class="flux-toolbar"><strong>FLUX.1 [schnell]</strong><span class="muted">{{ dirty ? '有未保存變更' : '設定已保留' }}</span><button class="secondary" :disabled="busy || loading" @click="choose('new')">新增 FLUX 草稿</button><button class="secondary" :disabled="busy || loading" @click="load(true)">{{ loading ? '讀取中…' : '同步 FLUX 元件' }}</button><button class="secondary" @click="emit('models')">元件版本與來源 →</button></div>
    <p class="notice warning">此專用流程尚未 GPU 驗證。請確認主模型是 FLUX.1 [schnell]、CLIP-L／T5／VAE 角色正確；目前不支援 FLUX LoRA、參考圖與負面提示詞。</p>
    <p class="footnote">原引擎：{{ form.engine_url || '讀取中' }} · 元件同步：{{ catalog?.synced_at ? new Date(catalog.synced_at).toLocaleString() : '尚未同步' }}。清單與版本來自原引擎／使用者登記，未驗證實際檔案。</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p><p v-if="message" class="notice" role="status">{{ message }}</p>
    <div v-if="pending" class="notice warning" role="alert"><p>載入會取代目前未保存的 FLUX 內容。</p><button class="secondary" @click="pending = null">繼續編輯</button> <button class="secondary" @click="apply(pending)">捨棄變更並載入 FLUX</button></div>
    <template v-if="origin"><p v-for="warning in origin.warnings" :key="warning" class="footnote">{{ warning }}</p><ComponentSnapshot :items="origin.component_metadata" /><RuntimeSnapshot :item="origin.runtime_metadata" /></template>
    <div class="flux-grid">
      <form class="panel flux-editor" aria-label="FLUX 創作設定" @submit.prevent="save()"><fieldset :disabled="busy">
        <label for="flux-title">FLUX 草稿名稱</label><input id="flux-title" v-model="form.title" required maxlength="100">
        <div v-for="role in fluxRoles" :key="role.key" class="flux-role"><label :for="'flux-' + role.key">{{ role.label }}</label><input :id="'flux-' + role.key" v-model="form[role.key]" :list="'flux-options-' + role.key" required maxlength="2048" autocomplete="off"><datalist :id="'flux-options-' + role.key"><option v-for="item in choices(role.category)" :key="item.name" :value="item.name" /></datalist><p class="footnote">版本 {{ model(role)?.version || '未知' }} · {{ model(role)?.listed ? '上次清單已列出，提交前仍會驗證' : '清單未確認；可手動填名稱保存草稿' }}</p></div>
        <label for="flux-prompt">FLUX 提示詞</label><textarea id="flux-prompt" v-model="form.prompt" maxlength="20000" rows="5" placeholder="例如：A peaceful mountain lake, soft morning light" />
        <div class="flux-size"><label for="flux-width">FLUX 寬度<input id="flux-width" v-model.number="form.width" type="number" min="64" max="8192" step="16" required></label><label for="flux-height">FLUX 高度<input id="flux-height" v-model.number="form.height" type="number" min="64" max="8192" step="16" required></label><label for="flux-steps">FLUX Steps<input id="flux-steps" v-model.number="form.steps" type="number" min="1" max="4" step="1" required></label></div>
        <label for="flux-seed">FLUX Seed</label><input id="flux-seed" v-model="form.seed" inputmode="numeric" pattern="[0-9]{1,20}" maxlength="20" required>
        <details><summary>精度與裝置設定</summary><label for="flux-dtype">主模型載入精度</label><select id="flux-dtype" v-model="form.weight_dtype"><option value="default">引擎預設（不指定轉換精度）</option><option value="fp8_e4m3fn">FP8 e4m3fn（未驗證）</option><option value="fp8_e5m2">FP8 e5m2（未驗證）</option></select><label for="flux-device">文字編碼器裝置</label><select id="flux-device" v-model="form.encoder_device"><option value="default">引擎預設</option><option value="cpu">CPU（未驗證效能）</option></select><p class="footnote">這些值會寫入原始 JSON；精度選擇不改寫模型檔案。VRAM／RAM 需求未知，尺寸有效不保證 GPU 可執行。</p></details>
        <p class="footnote">Euler / simple · CFG 1 · denoise 1 · batch 1 · 16 通道 latent。</p>
        <p v-if="problem" class="footnote" role="status">{{ problem }}</p>
        <div class="flux-actions"><button class="primary" type="submit" :disabled="!!problem || busy">保存 FLUX 草稿</button><button class="secondary" type="button" :disabled="!!problem || busy" @click="save(true)">另存新 FLUX 草稿</button><button class="secondary" type="button" :disabled="!!problem || busy" @click="downloadPreview">匯出 FLUX JSON</button></div>
        <details v-if="previewJson"><summary>上次匯出 JSON（可能不是目前設定）</summary><pre class="flux-json">{{previewJson}}</pre></details>
      </fieldset></form>
      <div><GenerationPanel :form="form" workflow="flux" :blocked-reason="block" :disabled="busy || loading" @gallery="emit('gallery', $event)" @restore-job="restore('flux/jobs/' + $event + '/creation-settings')" />
        <article class="panel"><h2>已保存 FLUX 草稿</h2><p v-if="!records.length" class="footnote">草稿與 SDXL 設定分開保存；保存不會生成圖片。</p><button v-for="record in records" :key="record.id" class="flux-draft" :disabled="busy" @click="choose(record)"><strong>{{ record.title }}</strong><span>{{ record.diffusion_model }} · {{ record.width }} × {{ record.height }} · {{ record.steps }} steps</span></button></article>
      </div>
    </div>
  </section>
</template>
<style scoped>
.flux-json{white-space:pre-wrap;overflow-wrap:anywhere;max-height:320px;overflow:auto;font-size:11px;line-height:1.7}
.flux-toolbar,.flux-actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:18px}.flux-toolbar{font-size:12px}.flux-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:22px}.flux-grid>div{min-width:0}.flux-editor fieldset{border:0;padding:0;margin:0;min-width:0}.flux-editor label{display:block;font-size:12px;margin:20px 0 10px}.flux-editor label:first-child{margin-top:0}.flux-editor input,.flux-editor select,.flux-editor textarea{width:100%;min-width:0;box-sizing:border-box}.flux-editor select,.flux-editor textarea{font:inherit;font-size:13px;border:1px solid var(--border-control);border-radius:7px;padding:12px;background:var(--surface-input);color:var(--text-primary)}.flux-editor textarea{line-height:1.8;resize:vertical}.flux-editor select:focus-visible,.flux-editor textarea:focus-visible{outline:2px solid var(--focus-ring);outline-offset:3px}.flux-size{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.flux-size input{margin-top:10px}.flux-editor details{margin-top:22px;border-top:1px solid var(--border-control);padding-top:18px}.flux-editor summary{cursor:pointer;font-size:12px}.flux-editor .flux-actions{margin-top:24px;margin-bottom:0}.flux-draft{display:block;text-align:left;width:100%;background:var(--surface-input);border:1px solid var(--border-control);border-radius:8px;padding:14px;margin-top:12px;color:var(--text-primary);overflow-wrap:anywhere}.flux-draft span{display:block;font-size:11px;color:var(--text-muted);margin-top:9px}.flux-role p{overflow-wrap:anywhere}@media(max-width:1100px){.flux-grid{grid-template-columns:1fr}}@media(max-width:650px){.flux-size{grid-template-columns:1fr}}
</style>
