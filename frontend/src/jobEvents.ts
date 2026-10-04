import { onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch, type Ref } from 'vue'
import type { LoraMetadataSnapshot } from './modelMetadata'

export type JobProgress = { node: string; current: number | null; max: number | null; percent: number | null; updated_at: string }
export type JobFailure = {
  code: string; title: string; message: string; suggestions: string[]
  node_id: string | null; node_type: string | null; exception_type: string | null
}
export type Job = { id: string; status: string; checkpoint: string; created_at: string; updated_at?: string; revision?: number; error?: string; progress?: JobProgress; failure_info?: JobFailure | null; lora_metadata?: LoraMetadataSnapshot[] | null; preflight_warnings?: string[] }
type Connection = { state: 'connecting' | 'connected' | 'reconnecting' | 'offline'; message?: string }
export const terminal = (job: Job) => ['completed', 'failed', 'cancelled', 'stopped'].includes(job.status)

// A REST snapshot may precede a transient, throttled progress event. Preserve
// the newer node sample at equal revisions without masking newer persisted state.
export function mergeJob(previous: Job | undefined, incoming: Job): Job {
  if (!previous) return incoming
  if ((incoming.revision ?? 0) < (previous.revision ?? 0)) return previous
  if ((incoming.revision ?? 0) === (previous.revision ?? 0) && previous.progress &&
      (!incoming.progress || previous.progress.updated_at > incoming.progress.updated_at)) {
    return { ...incoming, progress: previous.progress }
  }
  return incoming
}

export function useJobEvents(jobs: Ref<Job[]>, reload: () => Promise<void>) {
  const connections = ref<Record<string, Connection>>({})
  const visible = ref(false)
  const streams = new Map<string, EventSource>()
  const retries = new Map<string, number>()
  const retryTimers = new Map<string, ReturnType<typeof setTimeout>>()
  let active = false
  let mounted = false
  const eligible = () => jobs.value.filter(job => !terminal(job)).slice(0, 4)

  function close(id: string) {
    streams.get(id)?.close(); streams.delete(id)
    delete connections.value[id]
    const timer = retryTimers.get(id)
    if (timer) clearTimeout(timer)
    retryTimers.delete(id)
  }
  function stop() {
    for (const id of new Set([...streams.keys(), ...retryTimers.keys()])) close(id)
    visible.value = false
  }
  function open(id: string) {
    if (!visible.value || streams.has(id) || retryTimers.has(id) || (retries.get(id) ?? 0) >= 3) return
    connections.value[id] = { state: 'connecting' }
    const stream = new EventSource(`/api/jobs/${id}/events`)
    streams.set(id, stream)
    stream.addEventListener('job', event => {
      if (streams.get(id) !== stream) return
      try {
        const incoming = JSON.parse((event as MessageEvent).data).job as Job
        if (incoming?.id !== id || typeof incoming.status !== 'string') return
        jobs.value = jobs.value.map(job => job.id === id ? mergeJob(job, incoming) : job)
        if (terminal(incoming)) close(id)
      } catch { /* A broken event must not replace the last known job state. */ }
    })
    stream.addEventListener('connection', event => {
      if (streams.get(id) !== stream) return
      try {
        const connection = JSON.parse((event as MessageEvent).data) as Connection
        if (!['connected', 'reconnecting', 'offline'].includes(connection.state)) return
        connections.value[id] = connection
      } catch { /* Keep the last connection state. */ }
    })
    stream.onerror = () => {
      if (streams.get(id) !== stream) return
      close(id)
      const attempt = (retries.get(id) ?? 0) + 1
      retries.set(id, attempt)
      connections.value[id] = { state: attempt < 3 ? 'reconnecting' : 'offline', message: '進度連線中斷，保留上次進度；可刷新狀態或重新連線。' }
      if (attempt < 3 && visible.value && eligible().some(job => job.id === id)) {
        retryTimers.set(id, setTimeout(() => { retryTimers.delete(id); open(id) }, 2000 * 2 ** (attempt - 1)))
      }
    }
  }
  function sync() {
    if (!visible.value) return
    const targets = new Set(eligible().map(job => job.id))
    for (const id of new Set([...streams.keys(), ...retryTimers.keys()])) if (!targets.has(id)) close(id)
    for (const id of targets) open(id)
  }
  async function resume() {
    if (!active || document.visibilityState !== 'visible' || visible.value) return
    visible.value = true
    retries.clear()
    await reload().catch(() => {})
    sync()
  }
  function visibilityChanged() { if (document.visibilityState === 'visible') void resume(); else stop() }
  function reconnect() {
    stop(); retries.clear(); connections.value = {}
    void resume()
  }
  watch(() => jobs.value.map(job => `${job.id}:${job.status}`).join('|'), sync)
  onMounted(() => {
    mounted = true; active = true
    document.addEventListener('visibilitychange', visibilityChanged)
    void resume()
  })
  onActivated(() => { if (mounted) { active = true; void resume() } })
  onDeactivated(() => { active = false; stop() })
  onBeforeUnmount(() => { active = false; stop(); document.removeEventListener('visibilitychange', visibilityChanged) })
  return { connections, visible, reconnect }
}
