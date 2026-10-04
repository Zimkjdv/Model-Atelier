import type { CreationForm } from './creationSettings'
import type { Architecture } from './modelMetadata'

export const presetFields = [
  { key: 'width', label: '寬度' }, { key: 'height', label: '高度' },
  { key: 'steps', label: 'Steps' }, { key: 'cfg', label: 'CFG' },
  { key: 'sampler_name', label: 'Sampler' }, { key: 'scheduler', label: 'Scheduler' },
  { key: 'denoise', label: 'Denoise' },
] as const
export type PresetKey = typeof presetFields[number]['key']
export type PresetSettings = Pick<CreationForm, PresetKey>
export type ModelPreset = {
  id: string; name: string; description: string; validation: string
  reference: string; prompt_hint: string; settings: PresetSettings
}
export type ModelProfile = {
  engine_url: string; name: string; architecture: Architecture
  metadata_updated_at: string | null
  compatibility: { status: 'supported' | 'unknown' | 'unsupported'; message: string; allows_submission: boolean }
  preset: ModelPreset | null
  workflow: { id: 'checkpoint-text2image-v1'; name: string; fields: string[]; batch_size: 1; reference_images: false; lora: true; max_loras: 4; verification: string } | null
}

export function profileIdentity(profile: ModelProfile): string {
  return JSON.stringify([profile.engine_url, profile.name, profile.metadata_updated_at, profile.preset])
}

export function validateProfile(value: ModelProfile): ModelProfile {
  if (!value || typeof value.engine_url !== 'string' || typeof value.name !== 'string' ||
      !value.compatibility || !['supported', 'unknown', 'unsupported'].includes(value.compatibility.status) ||
      typeof value.compatibility.allows_submission !== 'boolean' || typeof value.compatibility.message !== 'string')
    throw new Error('模型工作流程資料格式無效，請重新更新。')
  const preset = value.preset
  const workflow = value.workflow
  const expectedFields = ['prompt', 'negative_prompt', 'seed', 'width', 'height', 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise', 'loras']
  if (value.compatibility.allows_submission ?
      !workflow || workflow.id !== 'checkpoint-text2image-v1' || typeof workflow.name !== 'string' ||
      workflow.batch_size !== 1 || workflow.reference_images !== false || workflow.lora !== true || workflow.max_loras !== 4 ||
      !Array.isArray(workflow.fields) || workflow.fields.length !== expectedFields.length ||
      new Set(workflow.fields).size !== expectedFields.length || !expectedFields.every(key => workflow.fields.includes(key)) : workflow !== null)
    throw new Error('流程欄位描述無效，已保留目前參數，請更新模型資料。')
  if (preset != null) {
    const settings = preset.settings
    if (!settings || typeof preset.id !== 'string' || typeof preset.name !== 'string' ||
        !['width', 'height'].every(key => {
          const number = settings[key as 'width' | 'height']
          return Number.isInteger(number) && number >= 64 && number <= 8192 && number % 8 === 0
        }) || !Number.isInteger(settings.steps) || settings.steps < 1 || settings.steps > 150 ||
        typeof settings.cfg !== 'number' || !Number.isFinite(settings.cfg) || settings.cfg < 0 || settings.cfg > 30 ||
        typeof settings.denoise !== 'number' || !Number.isFinite(settings.denoise) || settings.denoise < 0 || settings.denoise > 1 ||
        typeof settings.sampler_name !== 'string' || !settings.sampler_name ||
        typeof settings.scheduler !== 'string' || !settings.scheduler)
      throw new Error('模型預設參數格式無效，已保留目前設定。')
  }
  return value
}
