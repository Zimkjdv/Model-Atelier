export const imageWorkflowId = 'checkpoint-image2image-v1'
export type ReferenceFields = {
  workflow_mode: 'text2image' | 'image2image'
  image_asset_id: string | null
  reference_resize: 'fit' | 'stretch'
}
export type ReferenceAsset = { id: string; title: string; archived: boolean; purpose: string; width: number; height: number }
export type ReferenceSnapshot = ReferenceAsset & {
  sha256: string
  input_role?: 'source' | 'mask'
  preprocessing: { version: number; library_version: string } | null
  generation_preprocessing: { threshold?: number; white?: string; black?: string; version: number; library_version: string; resize: string; width: number; height: number; sha256: string }
}
export type ReferenceWorkflow = { id: string; name: string; implemented: boolean; input_requirement: string; control: string }
export const referenceDefaults: ReferenceFields = { workflow_mode: 'text2image', image_asset_id: null, reference_resize: 'fit' }
export const purposeLabel = (purpose: string) => ({ unspecified: '未指定', style: '視覺風格', character: '角色外觀', composition: '構圖' }[purpose] ?? '未知用途')
