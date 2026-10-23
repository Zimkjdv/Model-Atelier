export type MemorySnapshot = { total: number | null; free: number | null; used: number | null }
export type ResourceSamples = {
  schema_version: number
  source: string
  started_at: string
  ended_at: string | null
  end_reason: string | null
  interval_seconds: number
  retained_points: number
  attempts: number
  successes: number
  failures: number
  gaps: number
  last_error: string | null
  ram_max_used_bytes: number | null
  devices: {
    name: string | null
    type: string | null
    index: number | null
    max_used_bytes: number | null
  }[]
  samples: {
    at: string
    ram_used_bytes: number | null
    error: string | null
    devices: { device: number; used_bytes: number | null }[]
  }[]
  note: string
}
export type JobMeasurements = {
  schema_version: number
  engine_url: string
  dispatch_started_at: string | null
  terminal_observed_at: string | null
  dispatch_to_observation_seconds: number | null
  engine_execution_seconds: number | null
  task_vram_peak_bytes: number | null
  timing_note: string
  continuous_resources?: ResourceSamples | null
  resources_before_submission: {
    source: string
    captured_at: string
    status: string
    note: string
    ram: MemorySnapshot
    devices: {
      name: string | null
      type: string | null
      index: number | null
      vram: MemorySnapshot
      torch_vram: MemorySnapshot
    }[]
  } | null
}
