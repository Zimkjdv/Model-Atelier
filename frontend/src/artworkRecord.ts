import type { Ratings } from './artworkComparison'
import type { ExperimentContext } from './experimentSettings'
import type { ComponentSnapshot as ComponentMetadata } from './fluxSettings'
import type { JobMeasurements as Measurements } from './jobMeasurements'
import type { LoraMetadataSnapshot, ModelMetadataSnapshot } from './modelMetadata'
import type { ReferenceSnapshot as ReferenceMetadata } from './referenceSettings'
import type { RuntimeMetadata } from './runtimeMetadata'
import type { TemplateContext } from './templateContext'

type Parameters = {
  prompt: string | null
  negative_prompt: string | null
  seed: string | null
  steps: number | null
  cfg: number | null
  sampler: string | null
  scheduler: string | null
  denoise: number | null
}
export type Artwork = {
  template_context?: TemplateContext | null
  notes_truncated?: boolean
  experiment_context?: ExperimentContext | null
  measurements?: Measurements | null
  ratings: Ratings
  runtime_metadata?: RuntimeMetadata | null
  id: string
  job_id: string
  title: string
  checkpoint: string
  model_version: string
  model_metadata?: ModelMetadataSnapshot | null
  lora_metadata?: LoraMetadataSnapshot[] | null
  workflow_id?: string | null
  component_metadata?: ComponentMetadata[] | null
  reference_metadata?: ReferenceMetadata[] | null
  engine_url: string
  parameters: Parameters
  width: number
  height: number
  size: number
  created_at: string
  imported_at: string
  image_available: boolean
  thumbnail_available: boolean
  sha256: string
  favorite: boolean
  notes: string
  archived: boolean
  revision: number
  organization_updated_at: string | null
}
