import type { ModelMetadataSnapshot } from './modelMetadata'

export type LoraSetting = { name: string; enabled: boolean; strength_model: number; strength_clip: number }

export type GenerationFields = {
  loras: LoraSetting[]
  negative_prompt: string
  steps: number
  cfg: number
  sampler_name: string
  scheduler: string
  denoise: number
}

export type CreationForm = GenerationFields & {
  title: string
  prompt: string
  engine_url: string
  checkpoint: string
  width: number
  height: number
  seed: string
  reference_ids: string[]
}

export type ArtworkSettings = {
  artwork_id: string
  settings: CreationForm
  model_version: string
  warnings: string[]
  model_metadata?: ModelMetadataSnapshot | null
}

export type FailedJobSettings = {
  job_id: string
  settings: CreationForm
  model_version: string
  model_metadata: ModelMetadataSnapshot | null
  warnings: string[]
  availability: {
    current_engine_url: string
    engine_matches: boolean
    checkpoint_status: 'available' | 'missing' | 'unknown'
    catalog_synced_at: string | null
  }
}

export const generationDefaults: GenerationFields = {
  loras: [],
  negative_prompt: '', steps: 20, cfg: 7,
  sampler_name: 'euler', scheduler: 'normal', denoise: 1,
}

export function newCreation(): CreationForm {
  return { ...generationDefaults, title: '未命名創作', prompt: '', engine_url: '',
    checkpoint: '', width: 1024, height: 1024, seed: '0', reference_ids: [], loras: [] }
}
