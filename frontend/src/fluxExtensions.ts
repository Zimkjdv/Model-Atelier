import type { FluxForm } from './fluxSettings'
import type { Job } from './jobEvents'
import type { RuntimeMetadata } from './runtimeMetadata'

export const fluxLoraId = 'flux1-schnell-lora-v1'
export const fluxImageId = 'flux1-schnell-image2image-v1'
export const isFluxExtension = (id: unknown) => id === fluxLoraId || id === fluxImageId
export type FluxExtensionForm = Omit<FluxForm, 'workflow_id'> &
  (
    | { workflow_id: typeof fluxLoraId; lora_name: string; lora_strength: number }
    | {
        workflow_id: typeof fluxImageId
        image_asset_id: string
        denoise: number
        reference_resize: 'fit' | 'stretch'
      }
  )
export type FluxExtensionRestoration = Pick<
  Job,
  'component_metadata' | 'lora_metadata' | 'reference_metadata'
> & { settings: FluxExtensionForm; warnings: string[]; runtime_metadata?: RuntimeMetadata | null }
export function fluxExtensionSubmission(frozen: Record<string, unknown>) {
  if (!isFluxExtension(frozen.workflow_id))
    throw new Error('未知 FLUX 附加流程；未提交或轉為一般文生圖。')
  return { path: '/api/flux/extensions/generate', body: frozen }
}
