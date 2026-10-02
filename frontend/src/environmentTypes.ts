export type EnvironmentMemory = { total: number | null; used: number | null; free: number | null }
export type EnvironmentDevice = {
  name: string | null; type: string | null; index: string | number | null
  vram: EnvironmentMemory; torch_vram: EnvironmentMemory
}
export type EnvironmentSystem = {
  os?: string | null; python: string | null; pytorch: string | null; comfyui?: string | null
  cuda_runtime: string | null; cuda_available: boolean | null; driver: string | null
}
export type EngineDiagnostics = {
  scope: 'selected_engine'; source: 'ComfyUI /system_stats'; checked_at: string
  engine_url?: string; selected_engine_url?: string; matches_selected_engine?: boolean
  status: 'available' | 'offline' | 'invalid'
  system: EnvironmentSystem; ram: EnvironmentMemory; devices: EnvironmentDevice[]; warnings: string[]
}
export type EngineReport = {
  connected: boolean; url: string; error?: string; diagnostics?: EngineDiagnostics
  stats?: { system: { comfyui_version?: string; ram_total?: number; ram_free?: number }; devices: { name: string; vram_total?: number; vram_free?: number }[] }
}
export type LocalEnvironment = {
  scope: 'managed_local_comfyui'; source: string; python_path: string; checked_at: string | null
  status: 'not_checked' | 'available' | 'unavailable' | 'timeout'
  system: EnvironmentSystem; devices: EnvironmentDevice[]; warnings: string[]
}

export const environmentText = (value: string | null | undefined) => typeof value === 'string' && value.trim() ? value : '未知'
export const environmentSize = (value: number | null | undefined) => typeof value === 'number' && Number.isFinite(value) && value >= 0
  ? `${(value / 1024 ** 3).toFixed(2)} GiB` : '未知'
export const cudaStatus = (value: boolean | null | undefined) => value === true ? '可用' : value === false ? '不可用' : '未知'
export function environmentTime(value: string | null | undefined): string {
  if (!value) return '尚無檢查時間'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '時間未知' : date.toLocaleString()
}
