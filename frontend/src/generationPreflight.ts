import type { Directive } from 'vue'

export type FieldProblems = Record<string, string>
export type PreflightBlocker = { message: string; action?: 'settings' | 'models' | 'refresh' }
export type FieldLimits = {
  bounds?: Partial<Record<'steps' | 'cfg' | 'denoise', { min: number; max: number }>>
  samplers?: string[]
  schedulers?: string[]
}
export const fieldLabels: Record<string, string> = {
  title: '草稿名稱',
  prompt: '提示詞',
  negative_prompt: '負面提示詞',
  checkpoint: '模型',
  image_asset_id: '輸入圖片',
  mask_asset_id: '已保存遮罩',
  width: '寬度',
  height: '高度',
  seed: 'Seed',
  steps: 'Steps',
  cfg: 'CFG',
  denoise: '重繪強度',
  sampler_name: '取樣器',
  scheduler: 'Scheduler',
  diffusion_model: 'FLUX 主模型',
  clip_l: 'CLIP-L',
  t5xxl: 'T5',
  vae: 'VAE',
  lora_name: 'FLUX LoRA',
  lora_strength: 'LoRA 強度',
  ipadapter_name: 'IP-Adapter',
  clip_vision_name: '影像編碼器',
  reference_weight: '參考權重',
  reference_start: '開始比例',
  reference_end: '結束比例',
  control_net_name: '結構控制模型',
  control_strength: '控制強度',
  control_start: '控制開始比例',
  control_end: '控制結束比例',
  canny_low: 'Canny 低閾值',
  canny_high: 'Canny 高閾值',
  grow_mask_by: '遮罩擴張',
  feather_radius: '羽化半徑',
}

// Mirrors the common server input contract; workflow-specific validation remains in each studio.
export function generationFieldProblems(input: object, limits: FieldLimits = {}): FieldProblems {
  const value = input as Record<string, unknown>,
    errors: FieldProblems = {},
    flux = 'diffusion_model' in value
  const required = (key: string) => {
    if (typeof value[key] !== 'string' || !String(value[key]).trim())
      errors[key] = '請填寫或選擇' + (fieldLabels[key] || key) + '。'
  }
  required('title')
  for (const [key, max] of [
    ['title', 100],
    ['prompt', 20000],
    ['negative_prompt', 20000],
  ] as const)
    if (typeof value[key] === 'string' && value[key].length > max)
      errors[key] = '不可超過 ' + max + ' 字。'
  if (flux) {
    for (const key of ['diffusion_model', 'clip_l', 't5xxl', 'vae']) required(key)
    if (value.clip_l && value.clip_l === value.t5xxl)
      errors.t5xxl = 'CLIP-L 與 T5 必須使用不同元件。'
  } else required('checkpoint')
  if (
    value.workflow_mode === 'image2image' ||
    'mask_asset_id' in value ||
    'control_net_name' in value ||
    'ipadapter_name' in value ||
    value.workflow_id === 'flux1-schnell-image2image-v1'
  )
    required('image_asset_id')
  if ('mask_asset_id' in value) {
    required('mask_asset_id')
    if (value.image_asset_id && value.image_asset_id === value.mask_asset_id)
      errors.mask_asset_id = '原圖與遮罩不可使用同一張素材。'
  }
  if ('control_net_name' in value) required('control_net_name')
  if ('ipadapter_name' in value) {
    required('ipadapter_name')
    required('clip_vision_name')
  }
  if ('lora_name' in value) required('lora_name')
  if (
    typeof value.seed !== 'string' ||
    !/^[0-9]{1,20}$/.test(value.seed) ||
    BigInt(value.seed) > 18446744073709551615n
  )
    errors.seed = '請輸入 0–18446744073709551615 的十進位整數；以文字保留完整精度。'
  for (const key of ['width', 'height']) {
    const number = value[key],
      multiple = flux ? 16 : 8
    if (
      typeof number !== 'number' ||
      !Number.isInteger(number) ||
      number < 64 ||
      number > 8192 ||
      number % multiple !== 0
    )
      errors[key] = '需為 64–8192 之間、' + multiple + ' 的倍數。'
  }
  for (const [key, min, max, integer] of [
    ['steps', 1, flux ? 4 : 150, true],
    ['cfg', 0, 30, false],
    ['denoise', 0, 1, false],
    ['lora_strength', 0, 1, false],
  ] as const) {
    if (!(key in value)) continue
    const range =
      key === 'steps' || key === 'cfg' || key === 'denoise' ? limits.bounds?.[key] : undefined
    const low = Math.max(min, range?.min ?? min),
      high = Math.min(max, range?.max ?? max),
      number = value[key]
    if (
      typeof number !== 'number' ||
      !Number.isFinite(number) ||
      (integer && !Number.isInteger(number)) ||
      number < low ||
      number > high
    )
      errors[key] = `需為 ${low}–${high}${integer ? ' 的整數' : ''}。`
  }
  if (
    value.workflow_id === 'flux1-schnell-image2image-v1' &&
    (typeof value.denoise !== 'number' || value.denoise < 0.05 || value.denoise >= 1)
  )
    errors.denoise = '需大於等於 0.05 且小於 1。'
  for (const [key, options] of [
    ['sampler_name', limits.samplers],
    ['scheduler', limits.schedulers],
  ] as const) {
    if (!(key in value)) continue
    if (typeof value[key] !== 'string' || !/^[a-z][a-z0-9_]{0,63}$/.test(value[key]))
      errors[key] = '請選擇有效的引擎選項。'
    else if (options && !options.includes(value[key]))
      errors[key] = '目前引擎不支援此選項；請手動重新選擇。'
  }
  for (const [key, min, max, integer] of [
    ['reference_weight', 0, 2, false],
    ['grow_mask_by', 0, 64, true],
    ['feather_radius', 0, 64, true],
    ['control_strength', 0, 10, false],
  ] as const) {
    if (!(key in value)) continue
    const number = value[key]
    if (
      typeof number !== 'number' ||
      !Number.isFinite(number) ||
      number < min ||
      number > max ||
      (integer && !Number.isInteger(number)) ||
      (key === 'control_strength' && number === 0)
    )
      errors[key] =
        key === 'control_strength'
          ? '需大於 0 且不超過 10。'
          : `需為 ${min}–${max}${integer ? ' 的整數' : ''}。`
  }
  for (const [start, end, min, max] of [
    ['reference_start', 'reference_end', 0, 1],
    ['control_start', 'control_end', 0, 1],
    ['canny_low', 'canny_high', 0.01, 0.99],
  ] as const) {
    if (!(start in value) || (start === 'canny_low' && value.control_kind)) continue
    for (const key of [start, end]) {
      const number = value[key]
      if (typeof number !== 'number' || !Number.isFinite(number) || number < min || number > max)
        errors[key] = `需介於 ${min}–${max}。`
    }
    if (!errors[start] && !errors[end] && Number(value[start]) >= Number(value[end]))
      errors[end] = '結束值需大於開始值。'
  }
  return errors
}

// A directive owns only its adjacent error node and accessibility attributes.
const nodes = new WeakMap<HTMLElement, HTMLElement>()
function updateField(element: HTMLElement, message: string | undefined, key?: string) {
  const id = (element.id || key || 'field') + '-preflight-error'
  let node = nodes.get(element)
  if (message && !node) {
    node = document.createElement('small')
    node.className = 'field-error'
    node.id = id
    element.insertAdjacentElement('afterend', node)
    nodes.set(element, node)
  }
  if (node) {
    node.textContent = message || ''
    node.hidden = !message
  }
  element.dataset.preflightField = key || element.id
  const described = (element.getAttribute('aria-describedby') || '')
    .split(/\s+/)
    .filter((token) => token && token !== id)
  if (message) described.push(id)
  if (described.length) element.setAttribute('aria-describedby', described.join(' '))
  else element.removeAttribute('aria-describedby')
  if (message) element.setAttribute('aria-invalid', 'true')
  else element.removeAttribute('aria-invalid')
}
export const vFieldError: Directive<HTMLElement, string | undefined> = {
  mounted: (element, binding) => updateField(element, binding.value, binding.arg),
  updated: (element, binding) => updateField(element, binding.value, binding.arg),
  beforeUnmount: (element) => {
    nodes.get(element)?.remove()
    nodes.delete(element)
  },
}
export function focusPreflightField(submitTarget: string | undefined, key: string) {
  const root = submitTarget
    ? document.querySelector(submitTarget)?.closest('.studio-settings')
    : null
  const element = root?.querySelector<HTMLElement>('[data-preflight-field="' + key + '"]')
  if (!element) return
  let parent = element.parentElement
  while (parent) {
    if (parent instanceof HTMLDetailsElement) parent.open = true
    parent = parent.parentElement
  }
  element.scrollIntoView({ block: 'center' })
  element.focus({ preventScroll: true })
}
