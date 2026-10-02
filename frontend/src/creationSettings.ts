export type GenerationFields = {
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
}

export const generationDefaults: GenerationFields = {
  negative_prompt: '', steps: 20, cfg: 7,
  sampler_name: 'euler', scheduler: 'normal', denoise: 1,
}

export function newCreation(): CreationForm {
  return { ...generationDefaults, title: '未命名創作', prompt: '', engine_url: '',
    checkpoint: '', width: 1024, height: 1024, seed: '0', reference_ids: [] }
}
