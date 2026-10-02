<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import GenerationPanel from './GenerationPanel.vue'
import ModelValidation from './ModelValidation.vue'
import GenerationAdvice from './GenerationAdvice.vue'
import { useStudioPreferences } from './studioPreferences'
import { generationDefaults, newCreation } from './creationSettings'
import type { ArtworkSettings, CreationForm, FailedJobSettings, GenerationFields } from './creationSettings'
import { architectureLabel } from './modelMetadata'
import { presetFields, profileIdentity, validateProfile } from './modelProfiles'
import type { ModelProfile } from './modelProfiles'
type Asset = { id: string; title: string; archived: boolean }
type Draft = Omit<CreationForm, keyof GenerationFields> & Partial<GenerationFields> & { id: string; revision: number; model_version: string; updated_at: string }
type Model = { name: string; listed: boolean; version?: string }
type Catalog = { engine_url: string; models: Model[]; selected: string | null }
type Range = { min: number; max: number }
type Capabilities = { engine_url: string; current_engine_url: string; engine_matches: boolean; available: boolean; stale: boolean; sampler_names: string[]; schedulers: string[]; bounds: Partial<Record<'steps' | 'cfg' | 'denoise', Range>>; synced_at: string | null; sync_error: string | null }
const emit = defineEmits<{ models: []; assets: []; gallery: [jobId: string] }>()
const props = defineProps<{ restoreRequest?: { artworkId: string; token: number } | null }>()
const form = reactive(newCreation())
const display = useStudioPreferences()
const id = ref<string | null>(null), revision = ref<number | null>(null), records = ref<Draft[]>([]), models = ref<Catalog | null>(null)
type Restoration = { kind: 'artwork'; value: ArtworkSettings } | { kind: 'job'; value: FailedJobSettings }
type SettingsOrigin = (ArtworkSettings & { kind: 'artwork' }) | (FailedJobSettings & { kind: 'job' })
const busy = ref(false), restoring = ref(false), error = ref(''), message = ref(''), saved = ref(JSON.stringify(form)), pending = ref<Draft | 'new' | Restoration | null>(null)
const origin = ref<SettingsOrigin | null>(null)
let restorationRequest = 0
const dirty = computed(() => JSON.stringify(form) !== saved.value)
const selected = computed(() => models.value?.engine_url === form.engine_url ? models.value.models.find(m => m.name === form.checkpoint) : undefined)
const draftVersion = ref('')
const references = ref<Asset[]>([])
const modelVersion = computed(() => draftVersion.value || selected.value?.version || '未知')
const available = computed(() => models.value?.engine_url === form.engine_url ? models.value.models.filter(m => m.listed) : [])
const capabilities = ref<Capabilities | null>(null), capabilityBusy = ref(false), capabilityError = ref('')
const profile = ref<ModelProfile | null>(null), profileBusy = ref(false), profileError = ref('')
const presetChoice = ref<string | null>(null)
let profileRequest = 0, profileAbort: AbortController | null = null
const matchingProfile = computed(() => profile.value?.engine_url === form.engine_url && profile.value.name === form.checkpoint ? profile.value : null)
const profileMessage = computed(() => matchingProfile.value?.compatibility.status === 'supported'
  ? '適用目前文生圖流程；登記架構尚未驗證實際檔案。'
  : matchingProfile.value?.compatibility.message ?? '')
const presetValidationLabel = computed(() => matchingProfile.value?.preset?.id === 'pony-v6-xl-rtx3060-landscape'
  ? '已驗：RTX 3060 單張風景'
  : '起始參數，尚未逐模型實測')
const presetReferenceUrl = computed(() => matchingProfile.value?.preset?.reference === 'docs/validation/pony-v6-xl-rtx3060.md'
  ? 'https://github.com/Zimkjdv/Model-Atelier/blob/main/docs/validation/pony-v6-xl-rtx3060.md'
  : '')
const presetRows = computed(() => matchingProfile.value?.preset ? presetFields.map(field => ({
  ...field, current: form[field.key], next: matchingProfile.value!.preset!.settings[field.key],
  changed: form[field.key] !== matchingProfile.value!.preset!.settings[field.key],
})) : [])
let capabilityRequest = 0
const matchingCapabilities = computed(() => capabilities.value?.engine_url === form.engine_url ? capabilities.value : null)
const samplers = computed(() => matchingCapabilities.value?.sampler_names ?? [])
const schedulers = computed(() => matchingCapabilities.value?.schedulers ?? [])
const submissionBlock = computed(() => {
  if (models.value && models.value.engine_url !== form.engine_url) return '此草稿使用的引擎與目前設定不同。請到設定頁連接原引擎，再更新模型庫。'
  if (form.checkpoint && profileBusy.value) return '正在確認模型工作流程資料，請稍候；草稿仍可保存。'
  if (form.checkpoint && !matchingProfile.value) return profileError.value || '尚未取得此模型的工作流程資料，請更新後再生成；草稿仍可保存。'
  if (matchingProfile.value && !matchingProfile.value.compatibility.allows_submission) return matchingProfile.value.compatibility.message
  if (capabilityBusy.value) return '正在更新引擎取樣選項，請稍候；草稿仍可保存。'
  const value = matchingCapabilities.value
  if (!value || !value.available) return '尚無此引擎的取樣能力資料。請啟動 ComfyUI 並更新引擎選項；草稿仍可保存。'
  if (!value.engine_matches) return '引擎設定已變更，請重新整理清單與引擎選項。'
  if (value.stale) return '引擎選項為上次快照，尚無法確認目前支援情況。請確認連線後更新；草稿仍可保存。'
  if (!samplers.value.includes(form.sampler_name)) return `目前引擎不支援取樣器 ${form.sampler_name}。已保留原設定，請手動選擇可用選項。`
  if (!schedulers.value.includes(form.scheduler)) return `目前引擎不支援 scheduler ${form.scheduler}。已保留原設定，請手動選擇可用選項。`
  for (const field of ['steps', 'cfg', 'denoise'] as const) {
    const range = value.bounds[field]
    if (range && (!Number.isFinite(form[field]) || form[field] < range.min || form[field] > range.max)) return `${field} 超出目前引擎與平台可用範圍 ${range.min}–${range.max}。已保留原設定供調整或保存。`
  }
  return ''
})
const aspect = computed(() => Number(form.width) > 0 && Number(form.height) > 0 ? `${form.width} / ${form.height}` : '1 / 1')
async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api/' + path, { method, ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : '請檢查名稱、尺寸、seed 與取樣設定：steps 1–150、CFG 0–30、denoise 0–1。')
  }
  return response.json()
}
function apply(record: Draft | 'new' | Restoration) {
  ++restorationRequest; restoring.value = false
  presetChoice.value = null
  if (typeof record === 'object' && 'kind' in record) {
    Object.assign(form, newCreation(), record.value.settings, { reference_ids: [...record.value.settings.reference_ids] })
    id.value = null; revision.value = null; draftVersion.value = record.value.model_version || '未知'
    origin.value = record.kind === 'artwork' ? { ...record.value, kind: 'artwork' } : { ...record.value, kind: 'job' }
    saved.value = ''; pending.value = null; error.value = ''
    message.value = record.kind === 'job'
      ? '失敗任務原設定已載入為新草稿。請手動調整，再按「生成圖片」建立新任務。'
      : '作品設定已載入為新草稿，請保存或調整後按「生成圖片」。'
    return
  }
  origin.value = null
  if (record === 'new') {
    Object.assign(form, newCreation(), { engine_url: models.value?.engine_url ?? '', checkpoint: models.value?.models.find(m => m.listed && m.name === models.value?.selected)?.name ?? '' })
    id.value = null; revision.value = null; draftVersion.value = ''
  } else {
    Object.assign(form, { ...generationDefaults, title: record.title, prompt: record.prompt, engine_url: record.engine_url, checkpoint: record.checkpoint, width: record.width, height: record.height, seed: record.seed, reference_ids: [...(record.reference_ids ?? [])], negative_prompt: record.negative_prompt ?? '', steps: record.steps ?? 20, cfg: record.cfg ?? 7, sampler_name: record.sampler_name ?? 'euler', scheduler: record.scheduler ?? 'normal', denoise: record.denoise ?? 1 })
    id.value = record.id; revision.value = record.revision; draftVersion.value = record.model_version || '未知'
  }
  saved.value = JSON.stringify(form); pending.value = null; error.value = ''; message.value = ''
}
function choose(record: Draft | 'new') {
  ++restorationRequest; restoring.value = false
  if (dirty.value) pending.value = record
  else apply(record)
}
async function restoreArtwork(request: { artworkId: string; token: number }) {
  const current = ++restorationRequest
  restoring.value = true; error.value = ''; message.value = ''
  try {
    const value = await api<ArtworkSettings>(`artworks/${request.artworkId}/creation-settings`)
    if (current !== restorationRequest || props.restoreRequest?.token !== request.token) return
    const record: Restoration = { kind: 'artwork', value }
    if (dirty.value) pending.value = record
    else apply(record)
  } catch (e) { if (current === restorationRequest && props.restoreRequest?.token === request.token) error.value = e instanceof Error ? e.message : '無法載入作品設定' }
  finally { if (current === restorationRequest) restoring.value = false }
}
async function restoreFailedJob(jobId: string) {
  if (busy.value || restoring.value || pending.value) return
  const current = ++restorationRequest
  restoring.value = true; error.value = ''; message.value = ''
  try {
    const value = await api<FailedJobSettings>(`jobs/${jobId}/creation-settings`)
    if (current !== restorationRequest) return
    if (value.job_id !== jobId) throw new Error('讀取的設定與指定失敗任務不同，已保留目前草稿。')
    const record: Restoration = { kind: 'job', value }
    if (dirty.value) pending.value = record
    else apply(record)
  } catch (e) { if (current === restorationRequest) error.value = e instanceof Error ? e.message : '無法載入失敗任務設定' }
  finally { if (current === restorationRequest) restoring.value = false }
}
watch(() => props.restoreRequest, request => { if (request) void restoreArtwork(request) }, { immediate: true })
async function refreshProfile() {
  const request = ++profileRequest
  profileAbort?.abort()
  profileAbort = null; profile.value = null; presetChoice.value = null; profileError.value = ''
  const engineUrl = form.engine_url, name = form.checkpoint
  if (!engineUrl || !name) { profileBusy.value = false; return }
  const controller = new AbortController()
  profileAbort = controller; profileBusy.value = true
  try {
    const query = new URLSearchParams({ engine_url: engineUrl, name })
    const response = await fetch('/api/models/profile?' + query, { signal: controller.signal })
    const data = await response.json()
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '無法確認模型工作流程資料。')
    const value = validateProfile(data as ModelProfile)
    if (value.engine_url !== engineUrl || value.name !== name) throw new Error('模型工作流程資料與目前選擇不同，請重新更新。')
    if (request === profileRequest && form.engine_url === engineUrl && form.checkpoint === name) profile.value = value
  } catch (e) {
    if (request === profileRequest && !controller.signal.aborted)
      profileError.value = e instanceof Error ? e.message : '無法確認模型工作流程資料。'
  } finally {
    if (request === profileRequest) { profileBusy.value = false; profileAbort = null }
  }
}
watch(() => [form.engine_url, form.checkpoint], () => { void refreshProfile() }, { immediate: true, flush: 'sync' })
function choosePreset() {
  const value = matchingProfile.value
  if (profileBusy.value || !value?.preset || !value.compatibility.allows_submission) return
  if (!presetRows.value.some(row => row.changed)) {
    message.value = '目前參數已符合此模型預設。'
    return
  }
  presetChoice.value = profileIdentity(value)
}
function confirmPreset() {
  const value = matchingProfile.value
  if (profileBusy.value || !value?.preset || !value.compatibility.allows_submission || presetChoice.value !== profileIdentity(value)) {
    presetChoice.value = null
    message.value = '模型資料已變更，請重新確認預設參數。'
    return
  }
  const settings = value.preset.settings
  form.width = settings.width; form.height = settings.height; form.steps = settings.steps
  form.cfg = settings.cfg; form.sampler_name = settings.sampler_name
  form.scheduler = settings.scheduler; form.denoise = settings.denoise
  presetChoice.value = null
  message.value = `已套用「${value.preset.name}」。請確認並保存草稿。`
}
async function refreshCapabilities(explicit = false) {
  const request = ++capabilityRequest
  capabilityBusy.value = true; capabilityError.value = ''
  try {
    const value = await api<Capabilities>(explicit ? 'engine/capabilities/sync' : 'engine/capabilities', explicit ? 'POST' : 'GET')
    if (request === capabilityRequest) capabilities.value = value
  } catch (e) {
    if (request === capabilityRequest) { capabilities.value = null; capabilityError.value = e instanceof Error ? e.message : '無法更新引擎選項' }
  } finally { if (request === capabilityRequest) capabilityBusy.value = false }
}
async function refresh() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    const [list, catalog, assets] = await Promise.all([api<Draft[]>('drafts'), api<Catalog>('models'), api<Asset[]>('assets'), refreshCapabilities()])
    records.value = list; models.value = catalog; references.value = assets
    if (!form.engine_url && !dirty.value) apply('new')
    await refreshProfile()
  } catch (e) { error.value = e instanceof Error ? e.message : '無法讀取草稿' }
  finally { busy.value = false }
}
async function save(copy = false) {
  if (busy.value) return
  busy.value = true; error.value = ''; message.value = ''
  try {
    const record = await api<Draft>(id.value && !copy ? 'drafts/' + id.value : 'drafts', id.value && !copy ? 'PUT' : 'POST', { ...form, revision: revision.value })
    apply(record)
    records.value = [record, ...records.value.filter(r => r.id !== record.id)]
    message.value = '草稿已保存到本機。尚未提交生成任務。'
  } catch (e) { error.value = e instanceof Error ? e.message : '保存失敗' }
  finally { busy.value = false }
}
function randomSeed() {
  const bytes = crypto.getRandomValues(new Uint32Array(2))
  form.seed = ((BigInt(bytes[0]!) << 32n) | BigInt(bytes[1]!)).toString()
}
function beforeUnload(event: BeforeUnloadEvent) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
onMounted(() => { void refresh(); window.addEventListener('beforeunload', beforeUnload) })
onBeforeUnmount(() => { window.removeEventListener('beforeunload', beforeUnload); ++profileRequest; ++restorationRequest; profileAbort?.abort() })
onActivated(() => { if (form.engine_url) void refresh() })
</script>

<template>
  <div class="studio">
    <div class="studio-toolbar"><span class="chip">創作草稿</span><span class="muted">{{ dirty ? '尚有未保存變更' : id ? '已保存 · 修訂 ' + revision : '新草稿' }}</span><button class="secondary" :disabled="busy || restoring" @click="choose('new')">＋ 新草稿</button><button class="secondary" :disabled="busy || restoring" @click="refresh">重新整理清單</button></div>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p><p v-if="message" class="notice" role="status">{{ message }}</p>
    <p v-if="restoring" class="notice" role="status">正在讀取原始創作設定…</p>
    <div v-if="pending" class="notice warning" role="alert"><p>載入其他草稿、作品或失敗任務設定會取代目前未保存的內容。</p><button class="secondary" :disabled="busy || restoring" @click="pending = null">繼續編輯</button> <button class="secondary" :disabled="busy || restoring" @click="apply(pending)">捨棄變更並載入</button></div>
    <div v-if="origin" class="notice" role="status"><p>{{ origin.kind === 'job' ? '來源失敗任務 ' + origin.job_id.slice(0, 8) + ' · 提交時版本：' : '來源作品版本：' }}{{ origin.model_version }} · 已保留原引擎與生成設定。</p><p v-if="selected?.version && selected.version !== origin.model_version">模型庫目前登記版本：{{ selected.version }}。再次生成使用目前安裝的模型，請確認版本。</p><p v-for="warning in origin.warnings" :key="warning">{{ warning }}</p></div>
    <p v-if="display.error.value" class="notice" role="status">{{ display.error.value }}</p>
    <div class="studio-grid">
      <form class="panel editor" @submit.prevent="save()"><fieldset :disabled="busy || restoring">
        <label for="draft-title">草稿名稱</label><input id="draft-title" v-model="form.title" required maxlength="100">
        <label for="draft-model">Checkpoint 模型</label><select id="draft-model" v-model="form.checkpoint" @change="draftVersion = ''"><option value="">尚未選擇模型</option><option v-if="form.checkpoint && !available.some(m => m.name === form.checkpoint)" :value="form.checkpoint">{{ form.checkpoint }}（目前清單未列出）</option><option v-for="model in available" :key="model.name" :value="model.name">{{ model.name }}</option></select>
        <p class="footnote">模型版本：{{ modelVersion }} · {{ form.engine_url || '等待讀取引擎設定' }}</p>
        <p v-if="!available.length" class="inline-note">目前沒有可選的 checkpoint。仍可先保存創作草稿。 <button type="button" class="text-button" @click="emit('models')">前往模型庫 →</button></p>
        <p v-else-if="form.checkpoint && !selected?.listed" class="inline-note">這份草稿的模型未在目前清單中，保留原設定供整理。</p>
        <section v-if="form.checkpoint" class="model-profile" aria-label="模型工作流程與預設">
          <div class="profile-heading"><h3>模型工作流程</h3><button type="button" class="secondary" :disabled="profileBusy" @click="refreshProfile">{{ profileBusy ? '更新中…' : '更新模型資料' }}</button></div>
          <p v-if="profileBusy" role="status">正在確認此模型的登記架構與工作流程…</p>
          <p v-else-if="profileError || !matchingProfile" role="alert" class="profile-warning">{{ profileError || '尚無此模型的工作流程資料。' }}</p>
          <template v-else><p class="footnote">登記架構：{{ architectureLabel(matchingProfile.architecture) }}</p>
            <p :class="{ 'profile-warning': matchingProfile.compatibility.status !== 'supported' }" role="status">{{ profileMessage }}</p>
            <template v-if="matchingProfile.preset"><h3>{{ matchingProfile.preset.name }}</h3>
              <p class="footnote">{{ presetValidationLabel }}</p>
              <details class="preset-reference"><summary>預設來源與提示詞參考</summary>
                <p>{{ matchingProfile.preset.description }}</p><p class="footnote">{{ matchingProfile.preset.validation }}</p>
                <p v-if="presetReferenceUrl"><a :href="presetReferenceUrl" target="_blank" rel="noopener noreferrer">查看驗收紀錄 ↗</a></p>
                <p v-if="matchingProfile.preset.prompt_hint" class="profile-hint">提示詞參考：{{ matchingProfile.preset.prompt_hint }}</p>
              </details>
              <details v-if="!presetChoice" class="preset-differences"><summary>預設參數與目前設定</summary><table><thead><tr><th scope="col">參數</th><th scope="col">目前</th><th scope="col">預設</th></tr></thead><tbody><tr v-for="row in presetRows" :key="row.key" :class="{ changed: row.changed }"><th scope="row">{{ row.label }}</th><td>{{ row.current }}</td><td>{{ row.next }}</td></tr></tbody></table></details>
              <button v-if="!presetChoice" type="button" class="secondary apply-preset" :disabled="profileBusy || !matchingProfile.compatibility.allows_submission" @click="choosePreset">套用模型預設</button>
              <div v-else class="preset-confirm" role="alert"><p>套用預設將取代下方參數，請確認差異。</p><table><thead><tr><th scope="col">參數</th><th scope="col">目前</th><th scope="col">套用後</th></tr></thead><tbody><tr v-for="row in presetRows" :key="row.key" :class="{ changed: row.changed }"><th scope="row">{{ row.label }}</th><td>{{ row.current }}</td><td>{{ row.next }}</td></tr></tbody></table><div class="preset-actions"><button type="button" class="primary" :disabled="profileBusy" @click="confirmPreset">套用並取代上述參數</button><button type="button" class="secondary" @click="presetChoice = null">保留目前設定</button></div></div>
            </template><p v-else class="footnote">此模型尚無可套用的參數預設。</p>
          </template>
          <p v-if="matchingProfile?.preset" class="footnote">預設僅在確認後套用。</p>
        </section>
        <ModelValidation v-if="form.checkpoint" :engine-url="form.engine_url" :name="form.checkpoint" :refresh-key="matchingProfile?.metadata_updated_at || ''" />
        <label for="draft-prompt">畫面描述 <small>{{ form.prompt.length }} / 20000</small></label><textarea id="draft-prompt" v-model="form.prompt" maxlength="20000" rows="7" placeholder="描述角色、場景、光線與你想呈現的畫面…"></textarea>
        <label for="draft-negative">負面提示詞 <small>{{ form.negative_prompt.length }} / 20000</small></label><textarea id="draft-negative" v-model="form.negative_prompt" maxlength="20000" rows="3" placeholder="描述希望避免的畫面特徵…"></textarea>
        <div class="size-presets"><button v-for="preset in [{label:'正方形',w:1024,h:1024},{label:'直式',w:832,h:1216},{label:'橫式',w:1216,h:832}]" :key="preset.label" type="button" class="secondary" @click="form.width=preset.w;form.height=preset.h">{{ preset.label }}</button></div>
        <div class="size-fields"><label for="width">寬度<input id="width" v-model.number="form.width" type="number" min="64" max="8192" step="8" required></label><label for="height">高度<input id="height" v-model.number="form.height" type="number" min="64" max="8192" step="8" required></label></div>
                  <div class="size-fields"><label for="steps">Steps<input id="steps" v-model.number="form.steps" type="number" min="1" max="150" step="1" required></label><label for="cfg">CFG<input id="cfg" v-model.number="form.cfg" type="number" min="0" max="30" step="any" required></label></div>
        <details :open="display.value.references" @toggle="display.toggle('references', $event)"><summary>參考素材（{{ form.reference_ids.length }} / 8）</summary><p class="footnote">此階段僅保存素材關聯，尚未套用至生成流程。</p><button class="secondary" type="button" @click="emit('assets')">管理／上傳參考圖 →</button><div class="reference-list"><label v-for="asset in references.filter(a => !a.archived || form.reference_ids.includes(a.id))" :key="asset.id"><input v-model="form.reference_ids" type="checkbox" :value="asset.id" :disabled="!form.reference_ids.includes(asset.id) && form.reference_ids.length >= 8"><img :src="'/api/assets/' + asset.id + '/image'" :alt="asset.title">{{ asset.title }}{{ asset.archived ? '（已封存）' : '' }}</label></div><p v-if="!references.length" class="footnote">尚無素材，可先到參考素材頁上傳圖片。</p></details>
        <details :open="display.value.advanced" @toggle="display.toggle('advanced', $event)"><summary>進階設定</summary><label for="seed">Seed</label><div class="seed-field"><input id="seed" v-model="form.seed" inputmode="numeric" pattern="[0-9]{1,20}" required><button type="button" class="secondary" @click="randomSeed">隨機</button></div><p class="footnote">以文字精確保存 64 位元整數，避免瀏覽器數字精度造成變更。</p>
          <div class="inline-note" role="status"><p>{{ capabilityBusy ? '正在讀取 ComfyUI 取樣選項…' : matchingCapabilities?.available ? matchingCapabilities.stale ? '顯示上次引擎選項快照；尚未確認目前支援情況。' : '選項來自目前 ComfyUI 的 KSampler。' : '尚無此引擎的取樣選項資料。' }}</p><p v-if="matchingCapabilities?.synced_at" class="footnote">{{ matchingCapabilities.engine_url }} · 同步於 {{ new Date(matchingCapabilities.synced_at).toLocaleString() }}</p><p v-if="capabilityError || matchingCapabilities?.sync_error">{{ capabilityError || matchingCapabilities?.sync_error }}</p><button type="button" class="secondary" :disabled="capabilityBusy" @click="refreshCapabilities(true)">{{ capabilityBusy ? '更新中…' : '更新引擎選項' }}</button></div>

          <label for="sampler">Sampler</label><select id="sampler" v-model="form.sampler_name"><option v-if="!samplers.includes(form.sampler_name)" :value="form.sampler_name">{{ form.sampler_name }}（原設定，{{ matchingCapabilities?.available && !matchingCapabilities.stale ? '目前引擎未列出' : '尚未確認支援' }}）</option><option v-for="sampler in samplers" :key="sampler" :value="sampler">{{ sampler }}</option></select>
          <label for="scheduler">Scheduler</label><select id="scheduler" v-model="form.scheduler"><option v-if="!schedulers.includes(form.scheduler)" :value="form.scheduler">{{ form.scheduler }}（原設定，{{ matchingCapabilities?.available && !matchingCapabilities.stale ? '目前引擎未列出' : '尚未確認支援' }}）</option><option v-for="scheduler in schedulers" :key="scheduler" :value="scheduler">{{ scheduler }}</option></select>
          <label for="denoise">Denoise</label><input id="denoise" v-model.number="form.denoise" type="number" min="0" max="1" step="any" required><p class="footnote">草稿可保存原設定，生成前會重新確認引擎選項與參數範圍。</p><p v-if="matchingCapabilities?.available" class="footnote">{{ matchingCapabilities.stale ? '上次記錄的' : '目前' }}可用範圍：<template v-for="field in (['steps', 'cfg', 'denoise'] as const)" :key="field"><span v-if="matchingCapabilities.bounds[field]"> {{ field }} {{ matchingCapabilities.bounds[field]!.min }}–{{ matchingCapabilities.bounds[field]!.max }}；</span></template>平台上限不因引擎範圍變大而提高。</p>
        </details>
        <div class="save-actions"><button class="primary" :disabled="!form.engine_url">{{ busy ? '處理中…' : '保存草稿' }}</button><button v-if="id" type="button" class="secondary" @click="save(true)">另存新草稿</button></div>
      </fieldset></form>
      <div><GenerationAdvice :form="form" />
      <GenerationPanel :form="form" :blocked-reason="submissionBlock" :disabled="busy || restoring || !!pending" @gallery="emit('gallery', $event)" @restore-job="restoreFailedJob"/><article class="panel canvas-panel"><div class="panel-heading"><h2>畫布比例預覽</h2><span class="badge">{{ form.width }} × {{ form.height }}</span></div><div class="canvas-area"><div class="canvas" :style="{aspectRatio:aspect,width:`min(100%, ${Math.min(300, 320 * Number(form.width) / Number(form.height))}px)`}"><span>◈</span><p>為下一張作品留下構想</p><small>此處僅預覽比例，不是生成結果</small></div></div><p>使用「生成圖片」提交目前表單。保存草稿不會啟動 GPU 任務。</p></article>
      <article class="panel"><h2>已保存草稿 <span class="muted">{{ records.length }}</span></h2><p v-if="!records.length" class="muted">保存第一份草稿後，可以在這裡接續編輯。</p><button v-for="record in records" :key="record.id" class="draft-row" :class="{chosen:id===record.id}" :disabled="busy || restoring" @click="choose(record)"><strong>{{ record.title }}</strong><span>{{ record.width }} × {{ record.height }} · {{ new Date(record.updated_at).toLocaleString() }}</span><small>{{ record.checkpoint || '未選擇模型' }} · 版本 {{ record.model_version || '未知' }}</small></button></article></div>
    </div>
  </div>
</template>

<style scoped>
.reference-list label{display:flex;align-items:center;gap:10px;overflow-wrap:anywhere}.reference-list input{width:16px;flex-shrink:0}.reference-list img{width:48px;height:48px;object-fit:contain;flex-shrink:0}
.model-profile{border:1px solid #3d5143;background:#18231c;padding:16px;border-radius:9px;margin:18px 0;font-size:12px;overflow-wrap:anywhere}.model-profile h3{font-size:13px;margin:0}.profile-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.profile-heading button{font-size:11px;padding:8px 10px}.profile-warning{color:#ebc4a1}.profile-hint{font-family:monospace;white-space:pre-wrap;line-height:1.7}.model-profile table{width:100%;border-collapse:collapse;margin:12px 0;font-size:11px}.model-profile th,.model-profile td{text-align:left;border-bottom:1px solid #34473a;padding:9px 6px;overflow-wrap:anywhere}.model-profile tbody th{font-weight:normal;color:#9fb1a5}.model-profile tr.changed td:last-child{color:#daebcb;font-weight:bold}.preset-confirm{background:#26362a;border:1px solid #607857;border-radius:7px;padding:12px;margin-top:14px}.preset-actions{display:flex;gap:10px;flex-wrap:wrap}.apply-preset{margin-top:14px}.model-profile .preset-differences{margin-top:14px}
.studio-toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:22px;font-size:12px}.studio-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:22px}.editor fieldset{border:0;padding:0;margin:0;min-width:0}.editor label{display:block;font-size:12px;margin:22px 0 10px}.editor label:first-child{margin-top:0}.editor label small{float:right;color:#8a9990}.editor select,.editor textarea{width:100%;padding:12px;background:#101517;color:#e5ebe7;border:1px solid #4c5855;border-radius:7px;font:inherit;font-size:13px}.editor textarea{resize:vertical;line-height:1.8}.editor select:focus-visible,.editor textarea:focus-visible{outline:2px solid #adceb0;outline-offset:3px}.size-fields{display:grid;grid-template-columns:1fr 1fr;gap:15px}.size-fields label{margin:14px 0}.size-fields input{margin-top:10px}.size-presets,.seed-field,.save-actions{display:flex;gap:10px;flex-wrap:wrap}.size-presets{margin-top:18px}.seed-field{flex-wrap:nowrap}.seed-field input{min-width:0}.seed-field button{flex-shrink:0}.save-actions{margin-top:24px}.inline-note{background:#202b24;border-radius:7px;padding:12px;font-size:12px}.text-button{padding:0;background:none;color:#c5dfba;font-size:12px}.editor details{border-top:1px solid #35403a;padding-top:18px;margin-top:10px}.editor summary{font-size:12px;cursor:pointer}.canvas-area{min-height:310px;display:grid;place-items:center;padding:25px 0}.canvas{width:min(100%,300px);min-height:0;background:linear-gradient(150deg,#2d3b31,#141c1a);border:1px dashed #6b8169;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:12px;overflow:hidden}.canvas>span{font-size:35px;color:#aec5a1}.canvas p{font-size:12px}.canvas small{font-size:10px;color:#8c9e93}.canvas-panel>p{font-size:11px}.draft-row{display:block;width:100%;text-align:left;background:#13191a;border:1px solid #303d37;border-radius:8px;color:#d9e5dc;margin-top:12px;padding:14px;overflow-wrap:anywhere}.draft-row.chosen{border-color:#9ebc90}.draft-row span,.draft-row small{display:block;font-size:10px;color:#94a79a;margin-top:8px}.draft-row strong{font-size:13px}@media(max-width:1100px){.studio-grid{grid-template-columns:1fr}}@media(max-width:700px){.canvas-panel .panel-heading{align-items:start;flex-direction:column}.studio-toolbar .muted{flex-basis:60%}}
</style>
