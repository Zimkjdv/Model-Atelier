<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import ExperimentSnapshot from './ExperimentSnapshot.vue'
import { experimentForSubmission, type ExperimentLoad } from './experimentSettings'
import type { CreationForm } from './creationSettings'
import LoraSnapshot from './LoraSnapshot.vue'
import JobMeasurements from './JobMeasurements.vue'
import ComponentSnapshot from './ComponentSnapshot.vue'
import ReferenceSnapshot from './ReferenceSnapshot.vue'
import { inpaintWorkflowId, type InpaintForm } from './inpaintSettings'
import { imageWorkflowId } from './referenceSettings'
import { fluxWorkflowId, type FluxForm } from './fluxSettings'
import { mergeJob, terminal, useJobEvents, type Job } from './jobEvents'
const props = defineProps<{ form: CreationForm | FluxForm | InpaintForm; experiment?:ExperimentLoad|null; workflow?: 'flux' | 'inpaint'; blockedReason?: string; disabled?: boolean }>()
const checkpointForm = computed(() => 'checkpoint' in props.form ? props.form : null)
const pendingKey = props.workflow === 'flux' ? 'atelier-pending-flux-submission' : props.workflow === 'inpaint' ? 'atelier-pending-inpaint-submission' : 'atelier-pending-submission'
const generatePath = props.workflow === 'flux' ? '/api/flux/generate' : props.workflow === 'inpaint' ? '/api/inpaint/generate' : '/api/generate'
const imageMode = computed(() => checkpointForm.value?.workflow_mode === 'image2image')
const missingModel = computed(() => checkpointForm.value ? !checkpointForm.value.checkpoint || (imageMode.value ? (!checkpointForm.value.image_asset_id || (props.workflow === 'inpaint' && !('mask_asset_id' in props.form && props.form.mask_asset_id))) : !!checkpointForm.value.reference_ids.length) : !('diffusion_model' in props.form && props.form.diffusion_model))
const emit = defineEmits<{ gallery: [jobId: string]; restoreJob: [jobId: string]; busy:[value:boolean]; pending:[value:boolean] }>()
const jobs = ref<Job[]>([]), busy = ref(false), error = ref('')
const cancelChoice = ref<string | null>(null)
const stopChoice = ref<string | null>(null)
const pending = ref<Record<string, unknown> | null>(null)
try { pending.value = JSON.parse(localStorage.getItem(pendingKey) || 'null') } catch { /* No valid saved request. */ }
watch(busy,value => emit('busy',value),{immediate:true,flush:'sync'})
watch(pending,value => emit('pending',!!value),{immediate:true,flush:'sync'})
const labels: Record<string, string> = { uploading_input: '上傳輸入圖片中', validating: '確認模型中', submitting: '提交中', queued: '等待生成', running: '生成中', completed: '已完成', failed: '失敗', unknown: '結果待確認', cancelling: '確認取消中', cancel_unknown: '取消結果待確認', cancelled: '已取消排隊', stopping: '確認停止中', stop_unknown: '停止結果待確認', stopped: '已停止生成' }
async function request(path: string, method = 'GET', body?: unknown) {
  const response = await fetch('/api/' + path, { method, headers: { 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) })
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || '請檢查輸入參數或引擎連線')
  return data
}
async function load() {
  const incoming: Job[] = await request('jobs')
  jobs.value = incoming.filter(job => props.workflow === 'flux' ? job.workflow_id === fluxWorkflowId : props.workflow === 'inpaint' ? job.workflow_id === inpaintWorkflowId : !job.workflow_id || job.workflow_id === imageWorkflowId).map(job => mergeJob(jobs.value.find(previous => previous.id === job.id), job))
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
      const experiment = props.workflow === 'inpaint' ? null : experimentForSubmission(props.experiment,props.form)
      const candidate = { ...JSON.parse(JSON.stringify(props.form)), request_id: crypto.randomUUID(), ...(experiment ? {experiment} : {}) }
      // Do not make an unpersisted request eligible for the recovery path.
      localStorage.setItem(pendingKey, JSON.stringify(candidate))
      pending.value = candidate
    }
    const response = await fetch(generatePath, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pending.value) })
    const data = await response.json()
    // A received API response is conclusive; transport failures retain the exact request ID.
    if (response.ok || (response.status >= 400 && response.status < 500) || data.detail?.job_id) {
      localStorage.removeItem(pendingKey); pending.value = null
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
async function stop(job: Job) {
  if (busy.value) return
  busy.value = true; error.value = ''; stopChoice.value = null
  try { await request(`jobs/${job.id}/stop`, 'POST'); await load() }
  catch (e) { error.value = e instanceof Error ? e.message : '無法確認停止結果'; await load().catch(() => {}) }
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
    <p v-if="checkpointForm" class="footnote">Checkpoint {{ workflow === 'inpaint' ? '局部編輯' : imageMode ? '圖生圖' : '文生圖' }} · {{ form.steps }} steps · {{ checkpointForm.sampler_name }} / {{ checkpointForm.scheduler }} · CFG {{ checkpointForm.cfg }} · denoise {{ checkpointForm.denoise }} · 每次 1 張。工作流程與精確 seed 會保存到本機。</p>
    <p v-else class="footnote">FLUX.1 [schnell] · {{ form.steps }} steps · Euler / simple · CFG 1 · 每次 1 張。完整流程與四元件快照會保存到本機；GPU 尚未驗證。</p>
    <p v-if="!imageMode && checkpointForm?.reference_ids.length" class="notice warning">文生圖不使用參考素材，請先取消選取，或切換圖生圖流程。</p>
    <p v-else-if="checkpointForm && !checkpointForm.checkpoint" class="notice">請先安裝並同步 checkpoint，再選擇模型。</p>
    <p v-if="blockedReason" class="notice warning">{{ blockedReason }}</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <p v-if="pending?.experiment" class="footnote">恢復原請求會保留原比較組關聯與設定，不使用現在的表單或比較預覽。</p>
    <p v-if="pending" class="notice warning">尚有未確認的提交 {{ pending.request_id }}。恢復時使用原始參數，重複請求不會再次入列。請先確認原提交，再載入失敗任務的設定。</p>
    <button type="button" class="primary" :disabled="busy || disabled || (!pending && (missingModel || !!blockedReason))" @click="generate">{{ busy ? '處理中…' : pending ? '恢復原提交請求' : '生成圖片' }}</button>
    <button type="button" class="secondary" :disabled="busy" @click="refresh">更新任務狀態</button>
    <button v-if="jobs.some(j => !terminal(j))" type="button" class="secondary" :disabled="busy" @click="reconnect">重新連線進度</button>
    <p v-if="jobs.some(j => !terminal(j))" class="footnote">即時監聽最近 4 個未完成任務。離線時保留最後進度並低頻查詢；切換頁面或隱藏分頁會停止監聽。</p>
    <p v-if="!jobs.length" class="footnote">尚無任務。生成結果暫存於 ComfyUI output，平台保留歷史 JSON。</p>
    <div v-for="job in jobs" :key="job.id" class="job">
      <strong>{{ labels[job.status] || job.status }}</strong> · {{ job.checkpoint }}
      <p class="footnote">{{ new Date(job.created_at).toLocaleString() }} · {{ job.id }}</p>
      <p v-if="job.workflow_id === imageWorkflowId" class="footnote">單張圖生圖 · 原素材與前處理已凍結。</p>
      <p v-if="job.workflow_id === inpaintWorkflowId" class="footnote">局部編輯 · 原圖與遮罩已凍結；白色編輯、黑色保留。</p>
      <ExperimentSnapshot :item="job.experiment_context" />
      <LoraSnapshot v-if="checkpointForm" :items="job.lora_metadata" />
      <ComponentSnapshot :items="job.component_metadata" /><JobMeasurements :item="job.measurements" />
      <ReferenceSnapshot :items="job.reference_metadata" :job-id="job.id" :processed-ready="!!job.input_upload || job.status === 'completed'" />
      <details v-if="job.preflight_warnings?.length"><summary>提交時檢查提示（原紀錄）</summary><p class="footnote">以下為提交當時的提示，不代表目前狀態或後續實測結果。</p><p v-for="warning in job.preflight_warnings" :key="warning" class="footnote">{{ warning }}</p></details>
      <section v-if="job.status === 'failed' && job.failure_info" class="failure-info" aria-label="任務失敗說明">
        <h3>{{ job.failure_info.title }}</h3><p>{{ job.failure_info.message }}</p>
        <ul v-if="job.failure_info.suggestions.length"><li v-for="(suggestion, index) in job.failure_info.suggestions" :key="index">{{ suggestion }}</li></ul>
        <details v-if="job.failure_info.node_id || job.failure_info.node_type || job.failure_info.exception_type"><summary>技術識別資料</summary><dl>
          <template v-if="job.failure_info.node_id"><dt>節點 ID</dt><dd>{{ job.failure_info.node_id }}</dd></template>
          <template v-if="job.failure_info.node_type"><dt>節點類型</dt><dd>{{ job.failure_info.node_type }}</dd></template>
          <template v-if="job.failure_info.exception_type"><dt>錯誤類型</dt><dd>{{ job.failure_info.exception_type }}</dd></template>
        </dl></details>
      </section>
      <p v-else-if="job.error" role="status">{{ job.error }}</p>
      <div v-if="job.progress" class="node-progress">
        <p class="footnote">目前節點 {{ job.progress.node }} · {{ job.progress.percent == null ? '正在執行' : `${job.progress.percent}%（${job.progress.current} / ${job.progress.max}）` }}</p>
        <progress v-if="job.progress.percent != null" :value="job.progress.percent" max="100" :aria-label="`任務 ${job.id} 目前節點進度`"></progress>
        <p class="footnote">進度更新：{{ new Date(job.progress.updated_at).toLocaleTimeString() }}。{{ terminal(job) ? '這是最後記錄的節點進度，任務結果見上方狀態。' : '節點完成後仍需等待引擎確認整個任務。' }}</p>
      </div>
      <p v-if="!terminal(job)" class="footnote" role="status">{{ connections[job.id] ? connectionLabels[connections[job.id]!.state] : '使用狀態查詢' }}<template v-if="connections[job.id]?.message"> · {{ connections[job.id]!.message }}</template><template v-if="connections[job.id]?.state !== 'connected' && job.progress"> · 上次進度可能已過期</template></p>
      <template v-if="job.status === 'queued'"><button v-if="cancelChoice !== job.id" type="button" class="secondary" :disabled="busy" @click="cancelChoice = job.id">取消排隊</button><div v-else class="notice"><p>只移除這個任務的排隊項目。若它已開始執行，平台會保留任務並提示最新狀態。</p><button type="button" class="secondary" :disabled="busy" @click="cancelChoice = null">保留任務</button><button type="button" class="secondary" :disabled="busy" @click="cancel(job)">確認取消此任務</button></div></template>
      <button v-if="['cancelling', 'cancel_unknown'].includes(job.status)" type="button" class="secondary" :disabled="busy" @click="cancel(job)">確認取消結果</button>
      <template v-if="job.status === 'running'"><button v-if="stopChoice !== job.id" type="button" class="secondary" :disabled="busy" @click="stopChoice = job.id">停止此任務</button><div v-else class="notice warning"><p>只停止這個任務。需原引擎具備已驗證的指定任務停止能力；若已完成會保留結果，停止請求仍需歷史確認。</p><button type="button" class="secondary" :disabled="busy" @click="stopChoice = null">繼續生成</button><button type="button" class="secondary" :disabled="busy" @click="stop(job)">確認停止此任務</button></div></template>
      <button v-if="['stopping', 'stop_unknown'].includes(job.status)" type="button" class="secondary" :disabled="busy" @click="stop(job)">確認停止結果</button>
      <template v-if="job.status === 'failed' || ((workflow === 'flux' || job.workflow_id === imageWorkflowId || job.workflow_id === inpaintWorkflowId) && terminal(job))"><button type="button" class="secondary" :aria-label="`載入原設定並調整：${job.id}`" :disabled="busy || disabled || !!pending" @click="emit('restoreJob', job.id)">載入原設定並調整</button><p class="footnote">載入後可手動調整，再按「生成圖片」建立新任務。</p></template>
      <button v-if="job.status === 'completed'" class="secondary" @click="emit('gallery', job.id)">前往作品庫匯入圖片 →</button>
      <a :href="`/api/jobs/${job.id}/workflow`">下載完整工作流程</a> · <a :href="`/api/jobs/${job.id}`" target="_blank" rel="noopener">任務／歷史 JSON</a>
    </div>
  </article>
</template>
<style scoped>
button{margin:4px 8px 10px 0}.job{border-top:1px solid #35403a;padding:15px 0;font-size:12px;overflow-wrap:anywhere}.job a{color:#c5dfba}
.node-progress{margin:12px 0}progress{width:100%;height:8px;accent-color:#c5dfba}
.failure-info{background:#2c2720;border:1px solid #625342;border-radius:8px;padding:14px;margin:12px 0}.failure-info h3{font-size:13px;margin:0;color:#ebc4a1}.failure-info p{line-height:1.7}.failure-info ul{padding-left:20px;line-height:1.8}.failure-info details{margin-top:12px}.failure-info summary{cursor:pointer;color:#c8bba9}.failure-info dl{display:grid;grid-template-columns:auto 1fr;gap:8px 12px;font-size:11px}.failure-info dt{color:#b6a48d}.failure-info dd{margin:0;font-family:monospace}
</style>
