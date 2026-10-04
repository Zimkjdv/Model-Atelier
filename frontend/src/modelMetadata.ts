export const architectures = [
  { value: 'unknown', label: '未知' },
  { value: 'sd1', label: 'SD 1.x' },
  { value: 'sdxl', label: 'SDXL' },
  { value: 'sd3', label: 'SD 3.x' },
  { value: 'flux', label: 'FLUX' },
  { value: 'other', label: '其他' },
] as const

export type Architecture = typeof architectures[number]['value']
export type ModelMetadata = {
  architecture?: Architecture
  size_bytes?: number | null
  sha256?: string
  license_name?: string
  license_url?: string
  metadata_updated_at?: string | null
}
export type ModelMetadataSnapshot = ModelMetadata & {
  name: string
  version: string
  source_url: string
  origin: 'user_registered'
  captured_at: string
}
export type LoraMetadataSnapshot = ModelMetadataSnapshot & {
  enabled: true
  strength_model: number
  strength_clip: number
}

export function architectureLabel(value: unknown): string {
  return architectures.find(item => item.value === value)?.label ?? '未知'
}

export function validArchitecture(value: unknown): Architecture {
  return architectures.find(item => item.value === value)?.value ?? 'unknown'
}

export function fileSize(value: unknown): string {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) return '未知'
  return `${value.toLocaleString()} bytes · ${(value / 1024 ** 3).toFixed(3)} GiB`
}

export function fileHash(value: unknown): string {
  return typeof value === 'string' && /^[a-f0-9]{64}$/.test(value) ? value : '未知'
}

export function metadataTime(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) return '未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '未知' : date.toLocaleString()
}

export function safeMetadataUrl(value: unknown): string {
  if (typeof value !== 'string') return ''
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''
  } catch { return '' }
}

export function parseFileSize(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const number = Number(trimmed)
  if (!/^\d+$/.test(trimmed) || !Number.isSafeInteger(number) || number <= 0)
    throw new Error('檔案大小請輸入 1 至 9007199254740991 的整數 bytes，或留空表示未知。')
  return number
}
