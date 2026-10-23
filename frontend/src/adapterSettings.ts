import { newCreation, type CreationForm } from './creationSettings'
import type { ReferenceAsset } from './referenceSettings'
import type { ModelMetadataSnapshot } from './modelMetadata'

export const referenceWorkflowId = 'checkpoint-ipadapter-reference-v1'
export const referencePendingMarker = '_atelier_reference_workflow_id'
export type ReferenceForm = CreationForm & {
  workflow_mode: 'text2image'
  reference_resize: 'fit'
  reference_mode: 'style' | 'character'
  ipadapter_name: string
  clip_vision_name: string
  reference_weight: number
  reference_start: number
  reference_end: number
}
export type ReferenceComponent = ModelMetadataSnapshot & {
  role: string
  family?: string
  listed?: boolean
  notes?: string
}
export type ReferenceCatalog = {
  engine_url: string
  components: ReferenceComponent[]
  synced_at: string | null
  sync_error: string | null
}
export const referenceRoles = [
  {
    role: 'ipadapter',
    label: 'SDXL Plus ViT-H adapter',
    family: 'sdxl-plus-vit-h',
    architecture: 'sdxl',
    key: 'ipadapter_name',
  },
  {
    role: 'clip_vision',
    label: 'CLIP Vision ViT-H/14',
    family: 'clip-vit-h-14',
    architecture: 'other',
    key: 'clip_vision_name',
  },
] as const

export function newReference(): ReferenceForm {
  return {
    ...newCreation(),
    title: '未命名參考圖創作',
    workflow_mode: 'text2image',
    reference_resize: 'fit',
    reference_mode: 'style',
    ipadapter_name: '',
    clip_vision_name: '',
    reference_weight: 0.6,
    reference_start: 0,
    reference_end: 1,
  }
}

export function referenceSubmission(value: Record<string, unknown>) {
  if (
    !value ||
    Array.isArray(value) ||
    typeof value !== 'object' ||
    value[referencePendingMarker] !== referenceWorkflowId
  )
    throw new Error('待確認參考流程版本未知；未提交，請保留原紀錄。')
  const body = { ...value }
  delete body[referencePendingMarker]
  return { path: '/api/reference/generate', body }
}

export function referenceProblem(form: ReferenceForm, source?: ReferenceAsset): string {
  if (
    !source ||
    source.archived ||
    source.id !== form.image_asset_id ||
    JSON.stringify(form.reference_ids) !== JSON.stringify([source.id])
  )
    return '請選擇存在、未封存且關聯一致的參考素材。'
  if (
    !['style', 'character'].includes(form.reference_mode) ||
    form.workflow_mode !== 'text2image' ||
    form.denoise !== 1 ||
    form.reference_resize !== 'fit' ||
    form.loras.length
  )
    return '首版需選擇畫風或角色模式；固定空 latent、denoise 1、等比補白，不組合 LoRA。'
  if (!form.ipadapter_name.trim() || !form.clip_vision_name.trim())
    return '請選擇 adapter 與影像編碼器。'
  if (
    !form.title.trim() ||
    form.title.length > 100 ||
    form.prompt.length > 20000 ||
    form.negative_prompt.length > 20000
  )
    return '請確認名稱與提示詞長度。'
  if (
    [form.width, form.height].some((n) => !Number.isInteger(n) || n < 64 || n > 8192 || n % 8) ||
    form.width * form.height > 16000000
  )
    return '輸出尺寸需為 64–8192 的 8 倍數，且不超過 1600 萬像素。'
  if (
    typeof form.seed !== 'string' ||
    !/^(0|[1-9][0-9]{0,19})$/.test(form.seed) ||
    BigInt(form.seed) > 18446744073709551615n
  )
    return 'Seed 需為 64 位非負整數字串。'
  if (
    !Number.isInteger(form.steps) ||
    form.steps < 1 ||
    form.steps > 150 ||
    !Number.isFinite(form.cfg) ||
    form.cfg < 0 ||
    form.cfg > 30
  )
    return '請確認 Steps 1–150 與 CFG 0–30。'
  if (
    !Number.isFinite(form.reference_weight) ||
    form.reference_weight < 0 ||
    form.reference_weight > 2
  )
    return '參考權重需在 0–2；0 用於同流程無參考對照。'
  if (
    [form.reference_start, form.reference_end].some((n) => !Number.isFinite(n) || n < 0 || n > 1) ||
    form.reference_start >= form.reference_end
  )
    return '作用起始需小於結束，且介於 0–1。'
  return ''
}

export function registeredReferenceProblem(
  library: ReferenceCatalog | null,
  form: ReferenceForm,
): string {
  if (
    !library ||
    library.engine_url !== form.engine_url ||
    !library.synced_at ||
    library.sync_error
  )
    return '請先成功同步並登記參考元件。'
  for (const spec of referenceRoles) {
    const item = library.components.find((r) => r.role === spec.role && r.name === form[spec.key])
    if (
      !item?.listed ||
      item.family !== spec.family ||
      item.architecture !== spec.architecture ||
      !item.name.endsWith('.safetensors')
    )
      return spec.label + ' 需在同步清單並明確登記匹配家族、架構與 safetensors 格式。'
  }
  return ''
}

export function copyReference(value: ReferenceForm): ReferenceForm {
  try {
    const keys = Object.keys(newReference())
    if (
      !value ||
      Array.isArray(value) ||
      Object.keys(value).length !== keys.length ||
      keys.some((k) => !(k in value))
    )
      throw new Error()
    const raw = value as unknown as Record<string, unknown>
    if (
      [
        'title',
        'prompt',
        'negative_prompt',
        'engine_url',
        'checkpoint',
        'seed',
        'sampler_name',
        'scheduler',
        'ipadapter_name',
        'clip_vision_name',
      ].some((k) => typeof raw[k] !== 'string') ||
      !value.engine_url ||
      !value.checkpoint ||
      !value.image_asset_id ||
      !Array.isArray(value.loras) ||
      !Array.isArray(value.reference_ids)
    )
      throw new Error()
    const url = new URL(value.engine_url)
    if (
      !['http:', 'https:'].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    )
      throw new Error()
    if (
      referenceProblem(value, {
        id: value.image_asset_id,
        title: '',
        width: 0,
        height: 0,
        purpose: 'unspecified',
        archived: false,
      })
    )
      throw new Error()
    return JSON.parse(JSON.stringify(value))
  } catch {
    throw new Error('不是完整參考圖流程設定；未載入部分內容。')
  }
}
