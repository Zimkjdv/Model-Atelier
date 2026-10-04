import type { ModelMetadataSnapshot, LoraMetadataSnapshot } from './modelMetadata'
import type { RuntimeMetadata } from './runtimeMetadata'
import { referenceDefaults, type ReferenceFields, type ReferenceSnapshot } from './referenceSettings'

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

export type CreationForm = GenerationFields & ReferenceFields & {
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
  runtime_metadata?: RuntimeMetadata | null
  artwork_id: string
  settings: CreationForm
  model_version: string
  warnings: string[]
  model_metadata?: ModelMetadataSnapshot | null
  lora_metadata?: LoraMetadataSnapshot[] | null
  reference_metadata?: ReferenceSnapshot[] | null
}

export type FailedJobSettings = {
  runtime_metadata?: RuntimeMetadata | null
  job_id: string
  settings: CreationForm
  model_version: string
  model_metadata: ModelMetadataSnapshot | null
  lora_metadata: LoraMetadataSnapshot[] | null
  reference_metadata?: ReferenceSnapshot[] | null
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
  return { ...generationDefaults, ...referenceDefaults, title: '未命名創作', prompt: '', engine_url: '',
    checkpoint: '', width: 1024, height: 1024, seed: '0', reference_ids: [], loras: [] }
}
