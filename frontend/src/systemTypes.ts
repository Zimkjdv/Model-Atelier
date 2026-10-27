export type Memory = { total: number | null; used: number | null; free: number | null }
export type HostSystem = {
  runtime_kind?: 'native' | 'container'
  host: string
  os: string
  python: string
  updated_at: string
  gpus: (Memory & { index: string; name: string; driver: string })[]
  gpu_error: string | null
  ram: Memory
  disk: Memory & { path: string }
}
export type StorageReport = {
  checked_at: string
  warnings: string[]
  volumes: { id: string; path: string; total: number | null; free: number | null; status: string }[]
  directories: {
    id?: string
    role: string
    path: string
    resolved_path: string | null
    volume_id: string | null
    status: string
    error: string | null
    can_open?: boolean
  }[]
  folder_open_supported?: boolean
  totals: { total: number | null; free: number | null; volume_count: number; partial: boolean }
}
export const gb = (value: number | null | undefined) =>
  value == null || !Number.isFinite(value)
    ? '未知'
    : (value / 1e9).toLocaleString('zh-TW', { maximumFractionDigits: 1 }) + ' GB'
export const usedPercent = (value: Memory) =>
  value.total && value.used != null
    ? Math.min(100, Math.max(0, (value.used / value.total) * 100))
    : null
