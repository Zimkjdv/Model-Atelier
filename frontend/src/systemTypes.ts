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

export const storageCategoryNames = { models: '模型', artworks: '作品' } as const
export type StorageCategory = keyof typeof storageCategoryNames
type CategoryTotals = {
  status: 'complete' | 'partial' | 'unavailable'
  bytes: number | null
  observed_bytes: number | null
}
type ScanScope = {
  version: string
  roots: { category: StorageCategory; path: string }[]
  external_engine: boolean
  unavailable: StorageCategory[]
}
type StorageScan = {
  id: string
  status: 'queued' | 'running' | 'completed' | 'partial' | 'cancelled' | 'failed'
  scope: ScanScope
  started_at: string
  finished_at: string | null
  visited: number
  error: string | null
  stale_reason: string | null
  categories?: Record<StorageCategory, CategoryTotals>
  volumes?: ({ id: string; path: string } & Record<StorageCategory, number>)[]
  issue_count?: number
  issues?: { category: StorageCategory; path: string; message: string }[]
}
export type StorageCategoryReport = {
  scope: ScanScope
  scan: StorageScan | null
  last_completed: StorageScan | null
  last_result: StorageScan | null
  known: Partial<
    Record<StorageCategory, { bytes: number; checked_at: string; stale_reason: string | null }>
  >
}
export const categoryGb = (bytes: number | null | undefined) =>
  bytes && bytes < 1e8 ? '< 0.1 GB' : gb(bytes)
