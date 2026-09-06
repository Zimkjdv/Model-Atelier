<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
const props = defineProps<{ form: { engine_url: string; checkpoint: string; reference_ids: string[] } }>()
const emit = defineEmits<{ gallery: [jobId: string] }>()
type Job = { id: string; status: string; checkpoint: string; created_at: string; error?: string }
const jobs = ref<Job[]>([]), busy = ref(false), error = ref('')
const pending = ref<Record<string, unknown> | null>(null)
try { pending.value = JSON.parse(localStorage.getItem('atelier-pending-submission') || 'null') } catch { /* No valid saved request. */ }
const labels: Record<string, string> = { validating: '確認模型中', submitting: '提交中', queued: '等待生成', running: '生成中', completed: '已完成', failed: '失敗', unknown: '結果待確認' }
async function request(path: string, method = 'GET', body?: unknown) {
  const response = await fetch('/api/' + path, { method, headers: { 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) })
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || '請檢查輸入參數或引擎連線')
  return data
}
async function load() { jobs.value = await request('jobs') }
async function generate() {
  if (busy.value) return
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
    for (const job of jobs.value.filter(j => !['completed', 'failed'].includes(j.status))) await request(`jobs/${job.id}/refresh`, 'POST')
    await load()
  } catch (e) { error.value = e instanceof Error ? e.message : '查詢失敗' }
  finally { busy.value = false }
}
onMounted(() => { void load().catch(e => { error.value = e.message }) })
let timer = window.setInterval(() => { if (jobs.value.some(j => ['queued', 'running'].includes(j.status))) void refresh() }, 5000)
onBeforeUnmount(() => window.clearInterval(timer))
</script>
<template>
  <article class="panel">
    <h2>生成任務</h2>
    <p class="footnote">標準 checkpoint 文生圖 · 20 steps · Euler / normal · CFG 7 · 每次 1 張。工作流程與精確 seed 會保存到本機。</p>
    <p v-if="form.reference_ids.length" class="notice warning">尚未支援參考圖生成，請先取消素材選取。</p>
    <p v-else-if="!form.checkpoint" class="notice">請先安裝並同步 checkpoint，再選擇模型。</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <p v-if="pending" class="notice warning">尚有未確認的提交 {{ pending.request_id }}。恢復時使用原始參數，重複請求不會再次入列。</p>
    <button type="button" class="primary" :disabled="busy || (!pending && (!form.checkpoint || !!form.reference_ids.length))" @click="generate">{{ busy ? '處理中…' : pending ? '恢復原提交請求' : '生成圖片' }}</button>
    <button type="button" class="secondary" :disabled="busy" @click="refresh">更新任務狀態</button>
    <p v-if="!jobs.length" class="footnote">尚無任務。生成結果暫存於 ComfyUI output，平台保留歷史 JSON。</p>
    <div v-for="job in jobs" :key="job.id" class="job">
      <strong>{{ labels[job.status] || job.status }}</strong> · {{ job.checkpoint }}
      <p class="footnote">{{ new Date(job.created_at).toLocaleString() }} · {{ job.id }}</p>
      <p v-if="job.error" role="status">{{ job.error }}</p>
      <button v-if="job.status === 'completed'" class="secondary" @click="emit('gallery', job.id)">前往作品庫匯入圖片 →</button>
      <a :href="`/api/jobs/${job.id}/workflow`">下載完整工作流程</a> · <a :href="`/api/jobs/${job.id}`" target="_blank" rel="noopener">任務／歷史 JSON</a>
    </div>
  </article>
</template>
<style scoped>
button{margin:4px 8px 10px 0}.job{border-top:1px solid #35403a;padding:15px 0;font-size:12px;overflow-wrap:anywhere}.job a{color:#c5dfba}
</style>
