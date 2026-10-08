import type { ModelMetadataSnapshot } from './modelMetadata'

export const fluxWorkflowId = 'flux1-schnell-text2image-v1'
export type FluxForm = {
  workflow_id: typeof fluxWorkflowId; engine_url: string; title: string; diffusion_model: string
  clip_l: string; t5xxl: string; vae: string; prompt: string; seed: string
  width: number; height: number; steps: number
  weight_dtype: 'default' | 'fp8_e4m3fn' | 'fp8_e5m2'; encoder_device: 'default' | 'cpu'
}
export const fluxRoles = [
  { key: 'diffusion_model', category: 'diffusion_models', label: 'FLUX 主模型' },
  { key: 'clip_l', category: 'text_encoders', label: 'CLIP-L 編碼器' },
  { key: 't5xxl', category: 'text_encoders', label: 'T5 編碼器' },
  { key: 'vae', category: 'vae', label: 'VAE 元件' },
] as const
export type FluxComponent = ModelMetadataSnapshot & { listed: boolean; notes: string }
export type FluxCatalog = { engine_url: string; groups: Record<string, FluxComponent[]>; synced_at: string | null; sync_error: string | null }
export type ComponentSnapshot = ModelMetadataSnapshot & { role: string; category?: string; kind?: string }
export const newFlux = (engine_url = ''): FluxForm => ({ workflow_id: fluxWorkflowId, engine_url,
  title: 'FLUX 實驗', diffusion_model: '', clip_l: '', t5xxl: '', vae: '', prompt: '', seed: '0',
  width: 512, height: 512, steps: 4, weight_dtype: 'default', encoder_device: 'default' })
export function fluxProblem(v: FluxForm): string {
  if (!v.engine_url || !v.title.trim()) return '請確認引擎與草稿名稱。'
  if (fluxRoles.some(role => !v[role.key].trim())) return '請選擇或填寫四個 FLUX 元件名稱。'
  if (v.clip_l === v.t5xxl) return 'CLIP-L 與 T5 需選擇不同元件。'
  if (!/^[0-9]{1,20}$/.test(v.seed) || BigInt(v.seed) > 18446744073709551615n) return 'Seed 必須是 64 位非負十進位整數。'
  if (![v.width, v.height].every(n => Number.isInteger(n) && n >= 64 && n <= 8192 && n % 16 === 0)) return '尺寸需為 64–8192 且為 16 的倍數。'
  if (!Number.isInteger(v.steps) || v.steps < 1 || v.steps > 4) return 'Schnell 步數需為 1–4。'
  return ''
}
