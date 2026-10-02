<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import type { CreationForm } from './creationSettings'
import { mergeJob, terminal, useJobEvents, type Job } from './jobEvents'
const props = defineProps<{ form: CreationForm; blockedReason?: string; disabled?: boolean }>()
const emit = defineEmits<{ gallery: [jobId: string] }>()
const jobs = ref<Job[]>([]), busy = ref(false), error = ref('')
const cancelChoice = ref<string | null>(null)
const pending = ref<Record<string, unknown> | null>(null)
try { pending.value = JSON.parse(localStorage.getItem('atelier-pending-submission') || 'null') } catch { /* No valid saved request. */ }
const labels: Record<string, string> = { validating: '確認模型中', submitting: '提交中', queued: '等待生成', running: '生成中', completed: '已完成', failed: '失敗', unknown: '結果待確認', cancelling: '確認取消中', cancel_unknown: '取消結果待確認', cancelled: '已取消排隊' }
async function request(path: string, method = 'GET', body?: unknown) {
  const response = await fetch('/api/' + path, { method, headers: { 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) })
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || '請檢查輸入參數或引擎連線')
  return data
}
async function load() {
  const incoming: Job[] = await request('jobs')
  jobs.value = incoming.map(job => mergeJob(jobs.value.find(previous => previous.id === job.id), job))
}
const { connections, visible, reconnect } = useJobEvents(jobs, async () => {
  try { await load() } catch (e) { error.value = e instanceof Error ? e.message : '查詢失敗'; throw e }
})
const connectionLabels = { connecting: '正在連接即時進度', connected: '即時進度已連線', reconnecting: '即時進度重新連線中', offline: '即時進度暫不可用' }
async function generate() {
  if (busy.value || props.disabled || (!pending.value && props.blockedReason)) return
  busy.value = true; error.value = ''
  try {
    if (!pending.value) {
      pending.value = { ...JSON.parse(JSON.stringify(props.form)), request_id: crypto.randomUUID() }
      localStorage.setItem('atelier-pending-submission', JSON.stringify(pending.value))
    }
    const response = await fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pending.value) })
    const data = await response.json()
    // A received API response is conclusive; transport failures retain the exact request ID.
    if (response.ok || (response.status >= 400 && response.status < 500) || data.detail?.job_id) {
      localStorage.removeItem('atelier-pending-submission'); pending.value = null
    }
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || '生成參數無效')
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '提交失敗'
    if (pending.value) error.value += '。請保留原請求 ID 並使用下方恢復按鈕。'
    await load().catch(() => {})
  } finally { busy.value = false }
}
async function refresh() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    await load()
    const failures: string[] = []
    for (const job of jobs.value.filter(j => !terminal(j))) {
      try { await request(`jobs/${job.id}/refresh`, 'POST') }
      catch (e) { failures.push(`${job.id.slice(0, 8)}：${e instanceof Error ? e.message : '查詢失敗'}`) }
    }
    await load()
    error.value = failures.slice(0, 3).join('；') + (failures.length > 3 ? `；另有 ${failures.length - 3} 筆查詢失敗` : '')
  } catch (e) { error.value = e instanceof Error ? e.message : '查詢失敗' }
  finally { busy.value = false }
}
async function cancel(job: Job) {
  if (busy.value) return
  busy.value = true; error.value = ''; cancelChoice.value = null
  try { await request(`jobs/${job.id}/cancel`, 'POST'); await load() }
  catch (e) { error.value = e instanceof Error ? e.message : '無法確認取消結果'; await load().catch(() => {}) }
  finally { busy.value = false }
}
const timer = window.setInterval(() => {
  if (visible.value && jobs.value.some(j => !terminal(j) && connections.value[j.id]?.state !== 'connected')) void refresh()
}, 15000)
onBeforeUnmount(() => window.clearInterval(timer))
</script>
<template>
  <article class="panel">
    <h2>生成任務</h2>
    <p class="footnote">標準 checkpoint 文生圖 · {{ form.steps }} steps · {{ form.sampler_name }} / {{ form.scheduler }} · CFG {{ form.cfg }} · denoise {{ form.denoise }} · 每次 1 張。工作流程與精確 seed 會保存到本機。</p>
    <p v-if="form.reference_ids.length" class="notice warning">尚未支援參考圖生成，請先取消素材選取。</p>
    <p v-else-if="!form.checkpoint" class="notice">請先安裝並同步 checkpoint，再選擇模型。</p>
    <p v-if="blockedReason" class="notice warning">{{ blockedReason }}</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <p v-if="pending" class="notice warning">尚有未確認的提交 {{ pending.request_id }}。恢復時使用原始參數，重複請求不會再次入列。</p>
    <button type="button" class="primary" :disabled="busy || disabled || (!pending && (!form.checkpoint || !!form.reference_ids.length || !!blockedReason))" @click="generate">{{ busy ? '處理中…' : pending ? '恢復原提交請求' : '生成圖片' }}</button>
    <button type="button" class="secondary" :disabled="busy" @click="refresh">更新任務狀態</button>
    <button v-if="jobs.some(j => !terminal(j))" type="button" class="secondary" :disabled="busy" @click="reconnect">重新連線進度</button>
    <p v-if="jobs.some(j => !terminal(j))" class="footnote">即時監聽最近 4 個未完成任務。離線時保留最後進度並低頻查詢；切換頁面或隱藏分頁會停止監聽。</p>
    <p v-if="!jobs.length" class="footnote">尚無任務。生成結果暫存於 ComfyUI output，平台保留歷史 JSON。</p>
    <div v-for="job in jobs" :key="job.id" class="job">
      <strong>{{ labels[job.status] || job.status }}</strong> · {{ job.checkpoint }}
      <p class="footnote">{{ new Date(job.created_at).toLocaleString() }} · {{ job.id }}</p>
      <p v-if="job.error" role="status">{{ job.error }}</p>
      <div v-if="job.progress" class="node-progress">
        <p class="footnote">目前節點 {{ job.progress.node }} · {{ job.progress.percent == null ? '正在執行' : `${job.progress.percent}%（${job.progress.current} / ${job.progress.max}）` }}</p>
        <progress v-if="job.progress.percent != null" :value="job.progress.percent" max="100" :aria-label="`任務 ${job.id} 目前節點進度`"></progress>
        <p class="footnote">進度更新：{{ new Date(job.progress.updated_at).toLocaleTimeString() }}。{{ terminal(job) ? '這是最後記錄的節點進度，任務結果見上方狀態。' : '節點完成後仍需等待引擎確認整個任務。' }}</p>
      </div>
      <p v-if="!terminal(job)" class="footnote" role="status">{{ connections[job.id] ? connectionLabels[connections[job.id]!.state] : '使用狀態查詢' }}<template v-if="connections[job.id]?.message"> · {{ connections[job.id]!.message }}</template><template v-if="connections[job.id]?.state !== 'connected' && job.progress"> · 上次進度可能已過期</template></p>
      <template v-if="job.status === 'queued'"><button v-if="cancelChoice !== job.id" type="button" class="secondary" :disabled="busy" @click="cancelChoice = job.id">取消排隊</button><div v-else class="notice"><p>只移除這個任務的排隊項目。若它已開始執行，平台會保留任務並提示最新狀態。</p><button type="button" class="secondary" :disabled="busy" @click="cancelChoice = null">保留任務</button><button type="button" class="secondary" :disabled="busy" @click="cancel(job)">確認取消此任務</button></div></template>
      <button v-if="['cancelling', 'cancel_unknown'].includes(job.status)" type="button" class="secondary" :disabled="busy" @click="cancel(job)">確認取消結果</button>
      <button v-if="job.status === 'completed'" class="secondary" @click="emit('gallery', job.id)">前往作品庫匯入圖片 →</button>
      <a :href="`/api/jobs/${job.id}/workflow`">下載完整工作流程</a> · <a :href="`/api/jobs/${job.id}`" target="_blank" rel="noopener">任務／歷史 JSON</a>
    </div>
  </article>
</template>
<style scoped>
button{margin:4px 8px 10px 0}.job{border-top:1px solid #35403a;padding:15px 0;font-size:12px;overflow-wrap:anywhere}.job a{color:#c5dfba}
.node-progress{margin:12px 0}progress{width:100%;height:8px;accent-color:#c5dfba}
</style>
