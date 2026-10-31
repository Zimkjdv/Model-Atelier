<script setup lang="ts">
import {
  computed,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  reactive,
  ref,
  nextTick,
} from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'
import { newCreation, type CreationForm } from './creationSettings'
import { newFlux, type FluxCatalog, type FluxForm } from './fluxSettings'
import {
  generationFieldProblems,
  fieldLabels,
  vFieldError,
  type FieldLimits,
  type PreflightBlocker,
} from './generationPreflight'
import { validateProfile, type ModelProfile } from './modelProfiles'
import type { EngineReport } from './environmentTypes'
import { terminal, type Job } from './jobEvents'
import { useUnsavedChanges } from './unsavedChanges'
import {
  matchSimpleModel,
  simpleFluxComponents,
  simpleTemplates,
  simpleModelTemplates,
  simpleStyleTemplates,
  simpleStyleLora,
  simpleReferenceParts,
  type ListedModel,
  type SimpleTemplateId,
} from './simpleCreation'
import GenerationPanel from './GenerationPanel.vue'
import StudioPreview from './StudioPreview.vue'
import TemplateSnapshot from './TemplateSnapshot.vue'
import {
  newReference,
  referenceProblem,
  type ReferenceForm,
  type ReferenceCatalog,
} from './adapterSettings'
import type { ReferenceAsset } from './referenceSettings'
import AssetChoices from './AssetChoices.vue'
import SimpleStyleExample from './SimpleStyleExample.vue'
import referenceDemoImage from '../../docs/guide/images/examples/reference-source.png?url'
import SimpleExample from './SimpleExample.vue'
import { simpleExamples } from './simpleExamples'
import { presetEvidence } from './presetEvidence'
import { templateSelection, type TemplateSelection, type TemplateContext } from './templateContext'

const emit = defineEmits<{
  advanced: [
    settings: CreationForm | FluxForm | ReferenceForm,
    selection?: TemplateSelection | null,
  ]
  models: [category?: 'checkpoint' | 'flux' | 'lora' | 'reference']
  settings: []
  gallery: [jobId: string]
}>()
type Catalog = {
  engine_url: string
  models: ListedModel[]
  synced_at: string | null
  sync_error: string | null
}
type Capabilities = {
  engine_url: string
  engine_matches: boolean
  available: boolean
  stale: boolean
  sampler_names: string[]
  schedulers: string[]
  bounds?: FieldLimits['bounds']
}
const selectedId = ref<SimpleTemplateId>('animagine')
const selected = computed(() => simpleTemplates.find((item) => item.id === selectedId.value)!)
const variants = computed(() =>
  simpleTemplates.filter((item) => item.modelId === selected.value.modelId),
)
const checkpoint = reactive(newCreation())
const flux = reactive(newFlux())
const reference = reactive(newReference())
const form = computed(() =>
  selected.value.family === 'flux'
    ? flux
    : selected.value.family === 'reference'
      ? reference
      : checkpoint,
)
function prefillDescription() {
  Object.assign(form.value, {
    title: selected.value.title,
    prompt: selected.value.prompt,
    seed: selected.value.seed,
  })
  if ('negative_prompt' in form.value) form.value.negative_prompt = selected.value.negative
}
prefillDescription()
const aspectRatios = computed(() => [
  {
    label: '1:1',
    width: selected.value.family === 'flux' ? 512 : 1024,
    height: selected.value.family === 'flux' ? 512 : 1024,
  },
  { label: '3:4', width: 768, height: 1024 },
  { label: '16:9', width: 1280, height: 720 },
])
const assets = ref<ReferenceAsset[]>([])
const uploadBusy = ref(false)
const uploadInput = ref<HTMLInputElement | null>(null)
const loraCatalog = ref<{
  engine_url: string
  loras: ListedModel[]
  synced_at: string | null
  sync_error: string | null
} | null>(null)
const referenceCatalog = ref<ReferenceCatalog | null>(null)
const catalog = ref<Catalog | null>(null)
const fluxCatalog = ref<FluxCatalog | null>(null)
const engine = ref<EngineReport | null>(null)
const capabilities = ref<Capabilities | null>(null)
const engineUrl = ref('')
const profile = ref<ModelProfile | null>(null)
const loadedId = ref<SimpleTemplateId | null>(null)
const editing = ref(false)
const selection = computed<TemplateSelection | null>(() =>
  loadedId.value ? { template_id: loadedId.value, template_version: selected.value.version } : null,
)
const baseline = ref('')
const error = ref('')
const message = ref('')
const loading = ref(false)
const generating = ref(false)
const pending = ref(false)
const saving = ref(false)
const previewJob = ref<Job | null>(null)
const previewTemplate = ref<TemplateContext | null>(null)
const previewTemplateJob = ref('')
const savedJob = ref('')
const submittedForm = ref<{ id: string; signature: string } | null>(null)
const resultMatchesForm = computed(
  () =>
    submittedForm.value?.id === previewJob.value?.id &&
    submittedForm.value?.signature === JSON.stringify(form.value),
)
function submitted(id: string, settings: Record<string, unknown>) {
  submittedForm.value = {
    id,
    signature: JSON.stringify(
      Object.fromEntries(Object.keys(form.value).map((key) => [key, settings[key]])),
    ),
  }
}
const previewRevision = ref(0)
const reads = createRequestScope()
const profiles = createRequestScope()
const restores = createRequestScope()
const previewReads = createRequestScope()
let active = true
let templateEpoch = 0
const modified = computed(() => {
  if (!loadedId.value) return false
  if (selected.value.family !== 'reference') return JSON.stringify(form.value) !== baseline.value
  const original = JSON.parse(baseline.value || '{}')
  const current: Record<string, unknown> = { ...form.value }
  for (const item of [original, current]) {
    delete item.image_asset_id
    delete item.reference_ids
  }
  return JSON.stringify(current) !== JSON.stringify(original)
})
const unsaved = computed(() => !!loadedId.value && JSON.stringify(form.value) !== baseline.value)
useUnsavedChanges(
  unsaved,
  computed(() => saving.value || uploadBusy.value),
)
const locked = computed(() => generating.value || pending.value || saving.value || uploadBusy.value)
const step = computed(() =>
  !loadedId.value
    ? 1
    : generating.value || pending.value
      ? 3
      : !resultMatchesForm.value || previewTemplate.value?.selection.template_id !== loadedId.value
        ? 2
        : savedJob.value === previewJob.value?.id
          ? 4
          : previewJob.value?.status === 'completed'
            ? 4
            : previewJob.value && !terminal(previewJob.value)
              ? 3
              : 2,
)

function requirements() {
  const status = availability(selectedId.value)
  if (loading.value)
    return [{ key: 'loading', label: '正在檢查模型與引擎…', action: 'refresh' as const }]
  if (!engine.value || engine.value.url !== engineUrl.value || !engine.value.connected)
    return [
      {
        key: 'engine',
        label: '先啟動 ComfyUI，確認連線後按「重新檢查」。',
        action: 'settings' as const,
      },
    ]
  const inventory = selected.value.family === 'flux' ? fluxCatalog.value : catalog.value
  const items: { key: string; label: string; action: 'models' | 'refresh' | 'settings' }[] = []
  if (!inventory?.synced_at || inventory.sync_error)
    items.push({
      key: 'sync',
      label: '清單尚未同步或更新失敗，請到模型庫同步此分類。',
      action: 'models',
    })
  const expected =
    selected.value.family === 'flux'
      ? fluxMatches.value.map((part) => ({
          key: part.role,
          filename: part.filename,
          found: !!part.model,
          listed: fluxCatalog.value?.groups[part.category]?.some(
            (item) => item.listed && item.name === part.filename,
          ),
        }))
      : [
          {
            key: 'checkpoint',
            filename: selected.value.manifest!.filename,
            found: !!modelFor(selectedId.value),
            listed: catalog.value?.models.some(
              (item) => item.listed && item.name === selected.value.manifest!.filename,
            ),
          },
        ]
  for (const part of expected)
    if (!part.found)
      items.push({
        key: part.key,
        label: part.listed
          ? `${part.filename}：已列在清單，請核對版本與模型登記。`
          : `${part.filename}：清單中尚未找到相符項目，請先安裝並同步。`,
        action: 'models',
      })
  if (selected.value.task === 'lora' && !styleLora.value)
    items.push({
      key: 'lora',
      label: simpleStyleLora.filename + '：請安裝固定原生鍵名版本、同步 LoRA 並核對登記。',
      action: 'models',
    })
  if (selected.value.task === 'reference')
    for (const part of referenceMatches.value)
      if (!part.model)
        items.push({
          key: part.role,
          label: part.filename + '：請同步參考元件並核對雜湊及相容系列。',
          action: 'models',
        })
  if (!items.length && status !== '可載入配方')
    items.push({ key: 'unknown', label: status + '，請重新檢查。', action: 'refresh' })
  return items
}
function repair(action: 'models' | 'settings' | 'refresh') {
  if (action === 'models')
    emit(
      'models',
      !modelFor(selectedId.value) && selected.value.family !== 'flux'
        ? 'checkpoint'
        : selected.value.task === 'lora'
          ? 'lora'
          : selected.value.task === 'reference'
            ? 'reference'
            : selected.value.family === 'flux'
              ? 'flux'
              : 'checkpoint',
    )
  else if (action === 'settings') emit('settings')
  else void refresh(true)
}
async function editDescription() {
  editing.value = true
  await nextTick()
  document.getElementById('simple-prompt')?.focus()
}
async function preview(value: Job | null) {
  previewJob.value = value
  if (!active) return
  if (!value) {
    previewReads.cancel()
    previewTemplate.value = null
    previewTemplateJob.value = ''
    return
  }
  if (previewTemplateJob.value === value.id) return
  const read = previewReads.begin()
  previewTemplate.value = null
  previewTemplateJob.value = value.id
  try {
    const full = await apiJson<Job>('jobs/' + value.id, { signal: read.signal })
    if (read.isCurrent() && previewJob.value?.id === value.id)
      previewTemplate.value = full.template_context || null
  } catch (cause) {
    if (read.isCurrent()) {
      previewTemplateJob.value = ''
      error.value = '結果來源讀取失敗，請重新檢查或到任務資訊查看。'
    }
  }
}

function modelFor(id: SimpleTemplateId) {
  const template = simpleTemplates.find((item) => item.id === id)!
  return template.manifest && catalog.value?.engine_url === engineUrl.value
    ? matchSimpleModel(catalog.value.models, template.manifest, 'sdxl')
    : undefined
}
const fluxMatches = computed(() =>
  simpleFluxComponents.map((part) => ({
    ...part,
    model:
      fluxCatalog.value?.engine_url === engineUrl.value
        ? matchSimpleModel(
            fluxCatalog.value.groups[part.category] || [],
            part,
            part.role === 'diffusion_model' ? 'flux' : undefined,
          )
        : undefined,
  })),
)
const styleLora = computed(() =>
  loraCatalog.value?.engine_url === engineUrl.value
    ? matchSimpleModel(loraCatalog.value.loras, simpleStyleLora, 'sdxl')
    : undefined,
)
const referenceMatches = computed(() =>
  simpleReferenceParts.map((part) => ({
    ...part,
    model:
      referenceCatalog.value?.engine_url === engineUrl.value
        ? matchSimpleModel(
            referenceCatalog.value.components
              .filter((item) => item.role === part.role && item.family === part.family)
              .map((item) => ({ ...item, listed: item.listed === true })),
            part,
            part.architecture,
          )
        : undefined,
  })),
)
function availability(id: SimpleTemplateId): string {
  if (loading.value) return '檢查中'
  if (!engine.value || engine.value.url !== engineUrl.value) return '狀態未知'
  if (!engine.value.connected) return '引擎離線'
  if (simpleTemplates.find((item) => item.id === id)?.family === 'flux') {
    if (!fluxCatalog.value?.synced_at || fluxCatalog.value.sync_error) return '元件清單待同步'
    return fluxMatches.value.every((part) => part.model) ? '可載入配方' : '缺少相符元件登記'
  }
  if (!catalog.value?.synced_at || catalog.value.sync_error) return '模型清單待同步'
  if (!modelFor(id)) return '缺少相符模型登記'
  const template = simpleTemplates.find((item) => item.id === id)!
  if (
    template.task === 'lora' &&
    (!loraCatalog.value?.synced_at || loraCatalog.value.sync_error || !styleLora.value)
  )
    return '缺少相符 LoRA 登記'
  if (
    template.task === 'reference' &&
    (!referenceCatalog.value?.synced_at ||
      referenceCatalog.value.sync_error ||
      referenceMatches.value.some((item) => !item.model))
  )
    return '缺少相符參考元件'
  return '可載入配方'
}
const canLoad = computed(() => availability(selectedId.value) === '可載入配方' && !locked.value)

async function refresh(explicit = false) {
  if (!active || loading.value) return
  const read = reads.begin()
  loading.value = true
  error.value = ''
  profile.value = null
  try {
    const settings = await apiJson<{ comfy_url: string }>('settings', { signal: read.signal })
    const results = await Promise.allSettled([
      apiJson<EngineReport>('engine', { signal: read.signal }),
      apiJson<Catalog>('models', { signal: read.signal }),
      apiJson<FluxCatalog>('flux/components', { signal: read.signal }),
      apiJson<Capabilities>('engine/capabilities' + (explicit ? '/sync' : ''), {
        method: explicit ? 'POST' : 'GET',
        signal: read.signal,
      }),
      apiJson<NonNullable<typeof loraCatalog.value>>('loras', { signal: read.signal }),
      apiJson<ReferenceCatalog>('reference-components', { signal: read.signal }),
    ])
    const latest = await apiJson<{ comfy_url: string }>('settings', { signal: read.signal })
    if (!read.isCurrent()) return
    if (latest.comfy_url !== settings.comfy_url)
      throw new Error('引擎設定已變更，請重新檢查；目前描述已保留。')
    engineUrl.value = latest.comfy_url
    engine.value = results[0].status === 'fulfilled' ? results[0].value : null
    catalog.value = results[1].status === 'fulfilled' ? results[1].value : null
    fluxCatalog.value = results[2].status === 'fulfilled' ? results[2].value : null
    capabilities.value = results[3].status === 'fulfilled' ? results[3].value : null
    loraCatalog.value = results[4].status === 'fulfilled' ? results[4].value : null
    referenceCatalog.value = results[5].status === 'fulfilled' ? results[5].value : null
    if (engine.value?.diagnostics?.matches_selected_engine === false) engine.value = null
    if (catalog.value?.engine_url !== engineUrl.value) catalog.value = null
    if (fluxCatalog.value?.engine_url !== engineUrl.value) fluxCatalog.value = null
    if (results.some((result) => result.status === 'rejected'))
      error.value = '部分可用狀態讀取失敗，請重新檢查；無法確認的項目不會視為就緒。'
    if (loadedId.value && selected.value.family !== 'flux') await refreshProfile()
    if (previewJob.value && !previewTemplateJob.value) void preview(previewJob.value)
  } catch (cause) {
    if (read.isCurrent()) {
      engine.value = null
      catalog.value = null
      fluxCatalog.value = null
      capabilities.value = null
      error.value = cause instanceof Error ? cause.message : '無法讀取可用狀態。'
    }
  } finally {
    if (read.isCurrent()) loading.value = false
  }
}
async function refreshProfile() {
  const read = profiles.begin()
  const model = modelFor(selectedId.value)
  profile.value = null
  if (!model) return null
  const query = new URLSearchParams({ engine_url: engineUrl.value, name: model.name })
  const result = validateProfile(
    await apiJson<ModelProfile>('models/profile?' + query, { signal: read.signal }),
  )
  if (!read.isCurrent()) return null
  if (
    result.engine_url !== engineUrl.value ||
    result.name !== model.name ||
    result.preset?.id !== selected.value.presetId ||
    !result.compatibility.allows_submission
  )
    throw new Error('模型預設與此配方不符，請到模型庫核對登記；目前內容已保留。')
  profile.value = result
  return result
}
function selectTemplate(id: SimpleTemplateId) {
  if (locked.value || loading.value || id === selectedId.value) return
  if (unsaved.value && !window.confirm('切換配方會取代簡易創作的未保存設定，確定切換？')) return
  profiles.cancel()
  selectedId.value = id
  prefillDescription()
  loadedId.value = null
  editing.value = false
  baseline.value = ''
  profile.value = null
  message.value = ''
  error.value = ''
  previewJob.value = null
  previewReads.cancel()
  previewTemplate.value = null
  previewTemplateJob.value = ''
}
async function loadTemplate(edit = false) {
  if (!canLoad.value || loading.value) return
  if (unsaved.value && !window.confirm('重新載入配方會取代目前設定，確定載入？')) return
  loading.value = true
  const epoch = ++templateEpoch
  error.value = ''
  try {
    const template = selected.value
    if (template.family === 'flux') {
      const parts = Object.fromEntries(
        fluxMatches.value.map((part) => [part.role, part.model!.name]),
      )
      Object.assign(flux, newFlux(engineUrl.value), parts, {
        title: template.title,
        prompt: template.prompt,
        seed: template.seed,
        weight_dtype: 'fp8_e4m3fn',
        encoder_device: 'cpu',
      })
    } else {
      const result = await refreshProfile()
      if (!active || epoch !== templateEpoch || !result?.preset) return
      const target = template.family === 'reference' ? reference : checkpoint
      const inputId = reference.image_asset_id
      Object.assign(
        target,
        template.family === 'reference' ? newReference() : newCreation(),
        result.preset.settings,
        {
          engine_url: engineUrl.value,
          checkpoint: result.name,
          title: template.title,
          prompt: template.prompt,
          negative_prompt: template.negative,
          seed: template.seed,
        },
      )
      if (template.task === 'lora') {
        checkpoint.loras = [
          { name: styleLora.value!.name, enabled: true, strength_model: 1, strength_clip: 1 },
        ]
      }
      if (template.task === 'reference') {
        reference.image_asset_id = inputId
        reference.reference_ids = inputId ? [inputId] : []
        for (const part of referenceMatches.value)
          reference[part.role === 'ipadapter' ? 'ipadapter_name' : 'clip_vision_name'] =
            part.model!.name
      }
    }
    loadedId.value = template.id
    editing.value = edit
    baseline.value = JSON.stringify(form.value)
    message.value = edit
      ? '已套用配方，可修改英文描述後生成。'
      : '原配方已載入。可直接生成，或按「編輯描述」修改。'
    if (edit) await editDescription()
  } catch (cause) {
    if (active && epoch === templateEpoch)
      error.value = cause instanceof Error ? cause.message : '配方載入失敗。'
  } finally {
    if (active && epoch === templateEpoch) loading.value = false
  }
}
const blockers = computed<PreflightBlocker[]>(() => {
  const issues: PreflightBlocker[] = []
  if (!loadedId.value) issues.push({ message: '請先載入一份起始配方。' })
  if (!engine.value?.connected || engine.value.url !== engineUrl.value)
    issues.push({ message: '引擎離線或狀態未知，請確認連線後重新檢查。', action: 'settings' })
  if (form.value.engine_url && form.value.engine_url !== engineUrl.value)
    issues.push({ message: '配方來自不同引擎，請核對後重新載入配方。', action: 'settings' })
  if (availability(selectedId.value) !== '可載入配方')
    issues.push({
      message: availability(selectedId.value) + '；請在模型庫同步並核對架構及 SHA256。',
      action: 'models',
    })
  if (selected.value.family !== 'flux' && loadedId.value && !profile.value)
    issues.push({ message: '模型預設尚未確認，請重新檢查。', action: 'refresh' })
  if (
    selected.value.family !== 'flux' &&
    loadedId.value &&
    (!capabilities.value?.available ||
      capabilities.value.stale ||
      !capabilities.value.engine_matches ||
      capabilities.value.engine_url !== engineUrl.value)
  )
    issues.push({ message: '原引擎取樣選項尚未確認或已過期，請重新檢查。', action: 'refresh' })
  if (
    loadedId.value &&
    selected.value.family !== 'flux' &&
    modelFor(selectedId.value)?.name !== ('checkpoint' in form.value ? form.value.checkpoint : '')
  )
    issues.push({ message: '配方模型已不在相符登記中，請核對後重新載入。', action: 'models' })
  if (
    loadedId.value &&
    selected.value.family === 'flux' &&
    fluxMatches.value.some((part) => part.model?.name !== flux[part.role])
  )
    issues.push({ message: '配方元件登記已變更，請核對後重新載入。', action: 'models' })
  if (loadedId.value && selected.value.family === 'reference') {
    const problem = referenceProblem(
      reference,
      assets.value.find((item) => item.id === reference.image_asset_id),
    )
    if (problem) issues.push({ message: problem })
    if (
      referenceMatches.value.some(
        (part) =>
          part.model?.name !==
          reference[part.role === 'ipadapter' ? 'ipadapter_name' : 'clip_vision_name'],
      )
    )
      issues.push({ message: '參考元件登記已變更，請重新載入配方。', action: 'models' })
  }
  if (
    loadedId.value &&
    selected.value.task === 'lora' &&
    checkpoint.loras[0]?.name !== styleLora.value?.name
  )
    issues.push({ message: '原 LoRA 登記已變更，請重新載入配方。', action: 'models' })
  return issues
})
const fieldProblems = computed(() => {
  const c = capabilities.value
  const reliable =
    c?.available && c.engine_matches && !c.stale && c.engine_url === form.value.engine_url
  return generationFieldProblems(
    form.value,
    selected.value.family !== 'flux' && reliable
      ? { bounds: c.bounds, samplers: c.sampler_names, schedulers: c.schedulers }
      : {},
  )
})
const readiness = computed(() => {
  if (loading.value) return []
  const missing = requirements()
  if (missing.length) return missing.map((item) => ({ ...item, field: '' }))
  if (!loadedId.value)
    return [
      { key: 'recipe', label: '載入起始配方以確認模型與生成設定。', action: 'load', field: '' },
    ]
  return [
    ...blockers.value.map((item, index) => ({
      key: 'blocker-' + index,
      label: item.message,
      action: item.action || 'field',
      field: selected.value.family === 'reference' ? 'simple-reference' : 'simple-prompt',
    })),
    ...Object.entries(fieldProblems.value).map(([key, label]) => ({
      key,
      label: `${fieldLabels[key] || key}：${label}`,
      action: 'field',
      field: key,
    })),
  ]
})
async function completeRequirement() {
  if (locked.value || loading.value) return
  const item = readiness.value[0]
  if (!item) return
  if (item.action === 'load') await loadTemplate(true)
  else if (item.action === 'field') {
    if (item.field === 'simple-reference') document.getElementById(item.field)?.focus()
    else if (item.field === 'prompt' || item.field === 'simple-prompt') await editDescription()
    else transfer()
  } else repair(item.action as 'models' | 'settings' | 'refresh')
}
function setAspectRatio(width: number, height: number) {
  if (!loadedId.value || locked.value || loading.value) return
  form.value.width = width
  form.value.height = height
}
function randomSeed() {
  const words = crypto.getRandomValues(new Uint32Array(2))
  form.value.seed = ((BigInt(words[0]!) << 32n) | BigInt(words[1]!)).toString()
  message.value = '已更換 Seed；按「生成圖片」才會建立新任務。'
}
function transfer() {
  if (!loadedId.value || locked.value || loading.value) return
  emit('advanced', JSON.parse(JSON.stringify(form.value)), selection.value)
}
function chooseReference(id: string | null) {
  reference.image_asset_id = id
  reference.reference_ids = id ? [id] : []
}
async function uploadReference(file: File | Blob, name: string) {
  if (!loadedId.value || locked.value || selected.value.family !== 'reference') return
  if (file.size > 20 * 1024 * 1024) {
    error.value = '圖片不可超過 20 MiB。'
    return
  }
  uploadBusy.value = true
  error.value = ''
  try {
    const asset = await apiJson<ReferenceAsset>('assets?filename=' + encodeURIComponent(name), {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: file,
    })
    assets.value = [...assets.value.filter((item) => item.id !== asset.id), asset]
    chooseReference(asset.id)
    message.value = '參考圖片已上傳並選取；按生成才會建立任務。'
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '參考圖片上傳失敗。'
  } finally {
    uploadBusy.value = false
    if (uploadInput.value) uploadInput.value.value = ''
  }
}
async function uploadChosen(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) await uploadReference(file, file.name)
}
async function useDemoReference() {
  if (locked.value || !loadedId.value) return
  try {
    const response = await fetch(referenceDemoImage)
    if (!response.ok) throw new Error('範例圖片讀取失敗。')
    await uploadReference(await response.blob(), '自產畫風參考範例.png')
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '範例圖片讀取失敗。'
  }
}
async function saveResult() {
  const job = previewJob.value
  if (!job || job.status !== 'completed' || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const result = await apiJson<{
      imported: unknown[]
      existing: unknown[]
      errors: { message: string }[]
    }>('jobs/' + job.id + '/artworks', { method: 'POST' })
    if (result.errors.length) throw new Error(result.errors.map((item) => item.message).join('；'))
    if (!result.imported.length && !result.existing.length)
      throw new Error('此任務沒有可保存的結果。')
    savedJob.value = job.id
    previewRevision.value++
    message.value = '結果已存入作品庫，可離線查看。'
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : '保存結果無法確認，請到作品庫查看原任務。'
  } finally {
    saving.value = false
  }
}
async function restoreJob(id: string) {
  if (locked.value || loading.value) return
  loading.value = true
  error.value = ''
  const read = restores.begin()
  try {
    const prefix = selected.value.family === 'flux' ? 'flux/' : ''
    const value = await apiJson<{
      settings: CreationForm | FluxForm | ReferenceForm
      template_context?: TemplateContext | null
    }>(prefix + 'jobs/' + id + '/creation-settings', { signal: read.signal })
    if (read.isCurrent())
      emit('advanced', value.settings, templateSelection(value.template_context))
  } catch (cause) {
    if (read.isCurrent())
      error.value = cause instanceof Error ? cause.message : '無法載入原任務設定。'
  } finally {
    if (read.isCurrent()) loading.value = false
  }
}
let mounted = false
onMounted(() => {
  mounted = true
  void refresh()
})
onActivated(() => {
  active = true
  if (mounted && !loading.value) void refresh()
})
onDeactivated(() => {
  active = false
  ++templateEpoch
  reads.cancel()
  profiles.cancel()
  restores.cancel()
  previewReads.cancel()
  previewTemplateJob.value = ''
  loading.value = false
})
onBeforeUnmount(() => {
  active = false
  ++templateEpoch
  reads.dispose()
  profiles.dispose()
  restores.dispose()
  previewReads.dispose()
})
</script>

<template>
  <div class="simple-creation">
    <div class="simple-intro">
      <ol class="simple-steps" aria-label="創作進度">
        <li
          v-for="(label, index) in ['選擇配方', '確認或修改描述', '生成圖片', '保存成果']"
          :key="label"
          :aria-current="step === index + 1 ? 'step' : undefined"
          :class="{
            completed:
              step > index + 1 || (index === 3 && savedJob === previewJob?.id && step === 4),
          }"
        >
          <span aria-hidden="true">{{
            step > index + 1 || (index === 3 && savedJob === previewJob?.id && step === 4)
              ? '✓'
              : index + 1
          }}</span>
          <span class="simple-step-label">{{ label }}</span>
        </li>
      </ol>
      <button class="secondary" :disabled="loading || locked" @click="refresh(true)"
        >重新檢查</button
      >
    </div>
    <div class="simple-cards" role="group" aria-label="起始配方">
      <button
        v-for="item in simpleModelTemplates"
        :key="item.id"
        type="button"
        class="simple-card"
        :aria-pressed="selected.modelId === item.modelId"
        :disabled="loading || locked"
        @click="selectTemplate(item.id)"
      >
        <img
          class="simple-card-image"
          :src="simpleExamples[item.id]?.image"
          :alt="item.title + ' 原配方實際成果'"
        />
        <span class="simple-card-model">{{ item.model }}</span
        ><strong>{{ item.title }}</strong> <span>{{ item.description }}</span
        ><small
          class="simple-availability"
          :class="{ ready: availability(item.id) === '可載入配方' }"
          >{{ availability(item.id)
          }}{{ selected.modelId === item.modelId ? ' · 已選擇' : '' }}</small
        >
      </button>
    </div>
    <div class="simple-recipe-options">
      <div class="simple-style-cards" role="group" aria-label="畫風控制任務">
        <button
          v-for="item in simpleStyleTemplates"
          :key="item.id"
          class="secondary simple-variant simple-style-option"
          :class="{ unavailable: availability(item.id) !== '可載入配方' }"
          :title="item.description"
          :aria-pressed="selectedId === item.id"
          :disabled="loading || locked"
          @click="selectTemplate(item.id)"
        >
          <strong>{{ item.title }}</strong
          ><small> · {{ availability(item.id) }}</small>
        </button>
      </div>
      <section
        v-if="!selected.task"
        class="simple-variant-picker"
        aria-labelledby="simple-variant-heading"
      >
        <h3 id="simple-variant-heading">{{ selected.model }} 起始配方</h3>
        <div class="simple-variants" role="group" aria-label="模型內的起始配方">
          <button
            v-for="item in variants"
            :key="item.id"
            class="secondary simple-variant"
            :aria-pressed="selectedId === item.id"
            :disabled="loading || locked"
            :title="item.description"
            @click="selectTemplate(item.id)"
          >
            {{ item.title }}
          </button>
        </div>
      </section>
    </div>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <p v-if="message" class="notice" role="status">{{ message }}</p>
    <div class="simple-workbench">
      <section class="simple-editor panel" aria-label="簡易創作設定">
        <h3>{{ selected.title }}</h3
        ><p
          >原配方 v{{ selected.version }}；{{
            simpleExamples[selectedId]?.environment || selected.note
          }}</p
        >
        <div class="simple-load-actions">
          <button class="primary" :disabled="!canLoad || loading" @click="loadTemplate(false)">
            {{ loadedId ? '還原配方設定' : '載入起始配方' }}
          </button>
          <button
            v-if="!loadedId"
            class="secondary simple-edit-entry"
            :disabled="!canLoad || loading"
            @click="loadTemplate(true)"
            >套用後修改</button
          >
          <button
            v-else-if="!editing"
            class="secondary simple-edit-entry"
            :disabled="locked || loading"
            @click="editDescription"
            >編輯描述</button
          >
        </div>
        <fieldset :disabled="!loadedId || loading || locked">
          <template v-if="selected.family === 'reference'">
            <label for="simple-reference">參考圖片</label>
            <select
              id="simple-reference"
              :value="reference.image_asset_id || ''"
              @change="chooseReference(($event.target as HTMLSelectElement).value || null)"
            >
              <option value="">選擇一張圖片</option>
              <option
                v-for="asset in assets.filter(
                  (item) => !item.archived || item.id === reference.image_asset_id,
                )"
                :key="asset.id"
                :value="asset.id"
                :disabled="asset.archived"
                >{{ asset.title }}</option
              >
            </select>
            <input
              ref="uploadInput"
              id="simple-reference-upload"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              @change="uploadChosen"
            />
            <label for="simple-reference-upload">上傳自己的參考圖片</label>
            <button class="secondary" @click="useDemoReference">使用自產示範參考圖</button>
            <img
              v-if="reference.image_asset_id"
              class="simple-reference-preview"
              :src="'/api/assets/' + reference.image_asset_id + '/image'"
              alt="目前選取的參考圖片"
            />
            <label for="simple-reference-weight">參考程度 {{ reference.reference_weight }}</label>
            <input
              id="simple-reference-weight"
              v-model.number="reference.reference_weight"
              type="range"
              min="0"
              max="1"
              step="0.1"
            />
            <p class="footnote"
              >0 與 0.6
              有固定對照；其他程度屬修改設定，未逐值驗證畫質。參考可能同時帶入髮色、服裝及背景。
              參考圖由你選擇，屬任務輸入；換圖後不能視為示範原圖的重現。</p
            >
          </template>
          <label for="simple-prompt">實際生成提示詞（英文）</label>
          <textarea
            id="simple-prompt"
            v-model="form.prompt"
            :readonly="!editing"
            v-field-error:prompt="fieldProblems.prompt"
            rows="7"
            maxlength="20000"
            aria-describedby="simple-language"
          />
          <p id="simple-language" class="footnote"
            >直接修改英文提示詞。此處沒有自動翻譯；上方中文是配方說明。</p
          >
          <p v-if="loadedId && !editing" class="footnote"
            >目前保留原配方描述。要修改時按「編輯描述」；還原配方會恢復描述與固定 Seed。</p
          >
          <div class="simple-size">
            <span id="simple-ratio-label">比例</span>
            <div role="group" aria-labelledby="simple-ratio-label" class="simple-ratios">
              <button
                v-for="ratio in aspectRatios"
                :key="ratio.label"
                type="button"
                class="secondary"
                :aria-pressed="form.width === ratio.width && form.height === ratio.height"
                @click="setAspectRatio(ratio.width, ratio.height)"
                >{{ ratio.label }}</button
              >
            </div>
            <span class="simple-dimensions">{{ form.width }} × {{ form.height }}</span>
          </div>
          <p v-if="loadedId" class="footnote" role="status">{{
            modified ? '已修改配方，不沿用原配置的驗收結論。' : '使用原始配方設定。'
          }}</p>
          <div class="simple-actions">
            <button class="secondary" @click="randomSeed">換 Seed，準備再畫一張</button>
            <button class="secondary" @click="transfer">帶到進階工作台</button>
          </div>
        </fieldset>
        <div id="simple-submit" class="simple-submit"></div>
        <details v-if="loadedId" class="simple-recipe"
          ><summary>查看完整設定</summary>
          <p class="footnote"
            >配方版本 v1 · 登記匹配不代表目前權重已驗檔；新增範例的觀察另見下方紀錄。</p
          >
          <template v-if="profile?.preset && selected.family === 'checkpoint'">
            <p class="footnote">{{ presetEvidence(profile.preset, checkpoint).summary }}</p>
            <p class="footnote">{{
              presetEvidence(profile.preset, checkpoint).changes.join(' ')
            }}</p>
          </template>
          <pre>{{ JSON.stringify(form, null, 2) }}</pre>
        </details>
        <SimpleExample v-if="simpleExamples[selectedId]" :id="selectedId" :modified="modified" />
        <SimpleStyleExample v-if="selected.task" :task="selected.task" />
        <details v-if="selected.family === 'reference'" class="simple-recipe"
          ><summary>選擇其他已上傳素材</summary
          ><AssetChoices
            :selected-ids="reference.image_asset_id ? [reference.image_asset_id] : []"
            @items="assets = $event"
        /></details>
        <p v-if="loadedId" class="footnote">{{
          selected.family === 'reference'
            ? '圖片參考設定僅保留本頁；生成後可從任務或作品還原完整設定。'
            : '設定會在站內切頁時保留；重新整理前可帶到進階工作台保存草稿。'
        }}</p>
      </section>
      <div class="simple-stage">
        <p v-if="previewJob && loadedId && !resultMatchesForm" class="notice" role="status"
          >右側仍為既有任務結果，不代表目前表單的成果；修改描述不會更新舊圖。</p
        >
        <StudioPreview
          :key="selected.family + ':' + previewRevision"
          :job="previewJob"
          :width="form.width"
          :height="form.height"
          :family="previewJob?.checkpoint || selected.model"
          title="簡易創作"
          compact
          @gallery="emit('gallery', $event)"
        />
        <GenerationPanel
          :key="selected.family"
          preview-stage
          submit-target="#simple-submit"
          :form="form"
          :template-selection="selection"
          :workflow="
            selected.family === 'flux'
              ? 'flux'
              : selected.family === 'reference'
                ? 'reference'
                : undefined
          "
          :field-problems="fieldProblems"
          :blockers="blockers"
          :blocked-reason="blockers[0]?.message"
          :disabled="loading || saving || uploadBusy"
          @preview="preview"
          @submitted="submitted"
          @busy="generating = $event"
          @pending="pending = $event"
          @refresh-options="refresh(true)"
          @gallery="emit('gallery', $event)"
          @restore-job="restoreJob"
        >
          <template #preflight>
            <div
              v-if="readiness.length"
              class="notice warning simple-repair"
              aria-label="生成前需完成"
              role="status"
            >
              <p
                ><strong>還差 {{ readiness.length }} 項</strong>：{{ readiness[0]?.label }}</p
              >
              <button
                type="button"
                class="text-button simple-complete"
                :disabled="loading || locked"
                @click="completeRequirement"
              >
                {{
                  readiness[0]?.action === 'load'
                    ? '一鍵補齊 →'
                    : readiness[0]?.action === 'models'
                      ? '前往對應模型分類'
                      : readiness[0]?.action === 'settings'
                        ? '連線設定'
                        : readiness[0]?.action === 'refresh'
                          ? '重新檢查必要條件'
                          : '前往修正 →'
                }}
              </button>
              <details v-if="readiness.length > 1"
                ><summary>查看所有待辦</summary
                ><ul
                  ><li v-for="item in readiness" :key="item.key">{{ item.label }}</li></ul
                ></details
              >
            </div>
          </template>
          <template #actions>
            <div v-if="previewJob?.status === 'completed'" class="simple-result-actions">
              <button
                class="primary"
                :disabled="saving || savedJob === previewJob.id"
                @click="saveResult"
              >
                {{
                  saving ? '保存中…' : savedJob === previewJob.id ? '已存入作品庫' : '存入作品庫'
                }}
              </button>
              <button class="secondary" @click="emit('gallery', previewJob.id)">查看作品庫</button>
            </div>
          </template>
        </GenerationPanel>
        <TemplateSnapshot :item="previewTemplate" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.simple-creation {
  --accent: #b7e3a0;
  --ink3: #a6b8ac;
  max-width: 1600px;
  margin: auto;
  padding: 28px 32px 48px;
}
.simple-steps {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  padding: 0;
  margin: 0;
  list-style: none;
}
.simple-steps li {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink3);
  font-size: 14px;
}
.simple-steps li:not(:last-child)::after {
  content: '';
  width: 28px;
  height: 1px;
  margin: 0 4px;
  background: var(--line2);
}
.simple-steps li[aria-current='step'] {
  color: var(--accent);
  font-weight: 600;
}
.simple-steps li > span:first-child {
  display: grid;
  place-items: center;
  border: 1px solid var(--line2);
  border-radius: 50%;
  width: 26px;
  height: 26px;
  flex: 0 0 26px;
}
.simple-steps li[aria-current='step'] > span:first-child {
  border: 2px solid var(--accent);
}
.simple-steps .completed {
  color: var(--accent);
}
.simple-steps .completed > span:first-child {
  border-color: var(--accent);
  color: var(--aink);
  background: var(--accent);
}
.simple-edit-entry {
  margin: 0;
}
.simple-repair ul {
  padding-left: 18px;
}
.simple-repair li {
  margin-block: 12px;
  overflow-wrap: anywhere;
}
.simple-repair li span {
  display: block;
  margin-bottom: 8px;
}
.simple-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}
.simple-intro h2 {
  margin: 0 0 6px;
}
.simple-intro p {
  margin: 0;
  color: var(--ink2);
}
.simple-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.simple-card {
  display: flex;
  flex-direction: column;
  text-align: left;
  gap: 6px;
  padding: 14px;
  border: 1px solid var(--line2);
  border-radius: 16px;
  background: var(--panel);
  color: var(--ink);
}
.simple-card[aria-pressed='true'] {
  border-color: var(--accent);
  background: var(--asoft);
  box-shadow: inset 0 0 0 1px var(--accent);
}
.simple-card strong {
  font-size: 18px;
}
.simple-variant-picker {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  min-width: 0;
}
.simple-variant-picker h3 {
  font-size: 13px;
  color: var(--ink2);
  margin: 0;
  font-weight: 500;
}
.simple-recipe-options {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin: 24px 0;
}
.simple-style-cards {
  order: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-left: auto;
}
.simple-reference-preview {
  display: block;
  max-width: 100%;
  max-height: 240px;
  margin: 12px 0;
}
.simple-editor select {
  width: 100%;
  min-width: 0;
}
.simple-variants {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.simple-variant {
  white-space: normal;
}
.simple-style-option strong {
  font-weight: 500;
}
.simple-variant span {
  font-size: 12px;
  color: var(--ink2);
  line-height: 1.6;
}
.simple-variant[aria-pressed='true'] {
  border-color: var(--accent);
  background: var(--asoft);
}
.simple-card-image {
  width: 100%;
  height: clamp(110px, 11vw, 164px);
  object-fit: contain;
  background: var(--bg);
  border-radius: 8px;
}
.simple-card-model,
.simple-card small {
  color: var(--ink2);
  font-size: 13px;
}
.simple-availability {
  padding: 4px 12px;
  margin-top: 2px;
  border: 1px solid var(--line2);
  border-radius: 999px;
  align-self: flex-start;
}
.simple-availability.ready {
  color: var(--accent);
}
.simple-card span {
  line-height: 1.6;
}
.simple-workbench {
  display: grid;
  grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
  gap: 24px;
}
.simple-editor,
.simple-stage {
  min-width: 0;
}
.simple-stage {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
  align-self: start;
  gap: 0;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--panel);
  overflow: hidden;
}
.simple-stage > .notice,
.simple-stage > .simple-result-actions {
  margin: 0;
}
.simple-editor h3 {
  margin-top: 0;
  margin-bottom: 6px;
  font-size: 18px;
}
.simple-editor > p {
  color: var(--ink2);
  font-size: 13px;
  margin: 0 0 16px;
}
.simple-load-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.simple-editor fieldset {
  border: 0;
  padding: 0;
  margin: 20px 0 0;
  min-width: 0;
}
.simple-editor label {
  display: block;
  margin-bottom: 10px;
}
.simple-editor textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
}
.simple-size {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 13px;
  color: var(--ink2);
}
.simple-ratios {
  display: flex;
  gap: 8px;
}
.simple-dimensions {
  margin-left: auto;
}
.simple-actions,
.simple-result-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 16px 0;
}
.simple-repair {
  margin: 0 0 16px;
  padding: 12px 14px;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.simple-repair p {
  margin: 0;
}
.simple-repair details {
  margin-top: 8px;
}
.simple-repair button {
  margin: 4px 0 0;
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 4px;
}
.simple-recipe {
  margin-top: 20px;
}
.simple-recipe pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 360px;
  overflow: auto;
  font-size: 12px;
}
.simple-submit {
  margin-top: 20px;
}
@media (max-width: 900px) {
  .simple-creation {
    padding: 16px;
  }
  .simple-workbench {
    grid-template-columns: 1fr;
  }
  .simple-cards {
    grid-template-columns: 1fr;
  }
  .simple-intro {
    align-items: flex-start;
  }
}
</style>
