import type { CreationForm } from './creationSettings'
import type { FluxForm } from './fluxSettings'
export type CreationBundle = {
  kind: 'model-atelier-creation'; schema_version: 1
  workflow_id: 'checkpoint-text2image-v1' | 'checkpoint-image2image-v1' | 'flux1-schnell-text2image-v1'
  settings: CreationForm | FluxForm
  source_snapshot: null | { kind: 'artwork' | 'job'; id: string; model_version: string; workflow_json: string }
}
export type ImportPreview = { bundle: CreationBundle; warnings: string[] }

// A validated settings document contains JSON values, including a string seed.
// Serializing avoids structuredClone rejecting Vue proxies in emitted previews.
export function copySettings<T extends CreationForm | FluxForm>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}
