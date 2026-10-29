<script setup lang="ts">
import {
  fieldLabels,
  focusPreflightField,
  type FieldProblems,
  type PreflightBlocker,
} from './generationPreflight'
import { api as request, ApiError } from './apiClient'
import { submitOnce } from './generationRequest'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import ExperimentSnapshot from './ExperimentSnapshot.vue'
import { experimentForSubmission, type ExperimentLoad } from './experimentSettings'
import type { CreationForm } from './creationSettings'
import LoraSnapshot from './LoraSnapshot.vue'
import JobMeasurements from './JobMeasurements.vue'
import WorkflowFormatSupport from './WorkflowFormatSupport.vue'
import ComponentSnapshot from './ComponentSnapshot.vue'
import ControlSnapshot from './ControlSnapshot.vue'
import ControlEdgePreview from './ControlEdgePreview.vue'
import StructureOutput from './StructureOutput.vue'
import ReferenceComponentsSnapshot from './ReferenceComponentsSnapshot.vue'
import {
  referencePendingMarker,
  referenceSubmission,
  referenceWorkflowId,
  type ReferenceForm,
} from './adapterSettings'
import {
  controlEdgeWorkflowId,
  structureWorkflowId,
  controlPendingMarker,
  controlSubmission,
  isControlWorkflow,
  type ControlForm,
} from './controlSettings'
import ReferenceSnapshot from './ReferenceSnapshot.vue'
import {
  inpaintFeatherWorkflowId,
  fooocusWorkflowId,
  inpaintPendingMarker,
  inpaintSubmission,
  isInpaintWorkflow,
  type InpaintForm,
} from './inpaintSettings'
import { imageWorkflowId } from './referenceSettings'
import { fluxWorkflowId, type FluxForm } from './fluxSettings'
import { fluxExtensionSubmission, type FluxExtensionForm } from './fluxExtensions'
import { mergeJob, terminal, useJobEvents, type Job } from './jobEvents'
const props = defineProps<{
  form: CreationForm | FluxForm | FluxExtensionForm | InpaintForm | ControlForm | ReferenceForm
  experiment?: ExperimentLoad | null
  workflow?: 'flux' | 'flux-addon' | 'inpaint' | 'control' | 'reference'
  fieldProblems?: FieldProblems
  blockers?: PreflightBlocker[]
  blockedReason?: string
  previewStage?: boolean
  submitTarget?: string
  disabled?: boolean
}>()
const checkpointForm = computed(() => ('checkpoint' in props.form ? props.form : null))
const pendingKey = {
  checkpoint: 'atelier-pending-submission',
  flux: 'atelier-pending-flux-submission',
  'flux-addon': 'atelier-pending-flux-addon-submission',
  inpaint: 'atelier-pending-inpaint-submission',
  control: 'atelier-pending-control-submission',
  reference: 'atelier-pending-reference-submission',
}[props.workflow || 'checkpoint']
const imageMode = computed(
  () =>
    props.workflow === 'control' ||
    props.workflow === 'reference' ||
    checkpointForm.value?.workflow_mode === 'image2image',
)
const missingModel = computed(() =>
  checkpointForm.value
    ? !checkpointForm.value.checkpoint ||
      (imageMode.value
        ? !checkpointForm.value.image_asset_id ||
          (props.workflow === 'inpaint' &&
            !('mask_asset_id' in props.form && props.form.mask_asset_id))
        : !!checkpointForm.value.reference_ids.length)
    : !('diffusion_model' in props.form && props.form.diffusion_model),
)
const emit = defineEmits<{
  preview: [job: Job | null]
  refreshOptions: []
  gallery: [jobId: string]
  restoreJob: [jobId: string]
  busy: [value: boolean]
  pending: [value: boolean]
}>()
const previewId = ref('')
const previewJob = computed(
  () => jobs.value.find((job) => job.id === previewId.value) || jobs.value[0] || null,
)
const historyOpen = ref(false)
const jobs = ref<Job[]>([]),
  busy = ref(false),
  error = ref('')
watch(previewJob, (value) => emit('preview', value), { immediate: true, deep: true })
const cancelChoice = ref<string | null>(null)
const stopChoice = ref<string | null>(null)
const pending = ref<Record<string, unknown> | null>(null)
try {
  pending.value = JSON.parse(localStorage.getItem(pendingKey) || 'null')
} catch {
  /* No valid saved request. */
}
watch(busy, (value) => emit('busy', value), { immediate: true, flush: 'sync' })
watch(pending, (value) => emit('pending', !!value), { immediate: true, flush: 'sync' })
const hasFieldProblems = computed(() => Object.keys(props.fieldProblems || {}).length > 0)
const displayBlockers = computed(
  () => props.blockers || (props.blockedReason ? [{ message: props.blockedReason }] : []),
)
const submissionAvailability = computed(() => {
  if (pending.value) return '原提交待確認：恢復會沿用原 UUID 與參數。'
  if (busy.value || props.disabled) return '暫不可提交：正在載入、保存或處理中。'
  if (missingModel.value || props.blockedReason || hasFieldProblems.value)
    return '尚缺必要條件：請依下方提示補齊模型、素材或元件。'
  return '表單預檢可提交：按下生成後仍會檢查引擎與元件。'
})
const labels: Record<string, string> = {
  uploading_input: '上傳輸入圖片中',
  validating: '確認模型中',
  submitting: '提交中',
  queued: '等待生成',
  running: '生成中',
  completed: '已完成',
  failed: '失敗',
  unknown: '結果待確認',
  cancelling: '確認取消中',
  cancel_unknown: '取消結果待確認',
  cancelled: '已取消排隊',
  stopping: '確認停止中',
  stop_unknown: '停止結果待確認',
  stopped: '已停止生成',
}
const nextCursor = ref<string | null>(null),
  detailBusy = ref<string | null>(null)
const expanded = ref<string[]>([])
async function load(more = false) {
  const query = new URLSearchParams({ limit: '40', workflow: props.workflow || 'checkpoint' })
  if (more && nextCursor.value) query.set('cursor', nextCursor.value)
  const result = await request<{ items: Job[]; next_cursor: string | null }>(
    'library/jobs?' + query,
  )
  const incoming = result.items.map((job) => {
    const previous = jobs.value.find((value) => value.id === job.id)
    return mergeJob(previous, expanded.value.includes(job.id) ? { ...previous, ...job } : job)
  })
  const ids = new Set(jobs.value.map((job) => job.id))
  jobs.value = more ? [...jobs.value, ...incoming.filter((job) => !ids.has(job.id))] : incoming
  nextCursor.value = result.next_cursor
}
async function older() {
  if (busy.value || !nextCursor.value) return
  busy.value = true
  try {
    await load(true)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '讀取失敗'
  } finally {
    busy.value = false
  }
}
async function detail(job: Job) {
  if (detailBusy.value) return
  detailBusy.value = job.id
  try {
    const value = await request<Job>('jobs/' + job.id)
    jobs.value = jobs.value.map((item) => (item.id === job.id ? mergeJob(item, value) : item))
    if (!expanded.value.includes(job.id)) expanded.value.push(job.id)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '詳情讀取失敗'
  } finally {
    detailBusy.value = null
  }
}
const { connections, visible, reconnect } = useJobEvents(jobs, async () => {
  try {
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '查詢失敗'
    throw e
  }
})
const connectionLabels = {
  connecting: '正在連接即時進度',
  connected: '即時進度已連線',
  reconnecting: '即時進度重新連線中',
  offline: '即時進度暫不可用',
}
function freezeCurrentSubmission(): Record<string, unknown> {
  const experiment =
    props.workflow === 'inpaint' ||
    props.workflow === 'control' ||
    props.workflow === 'reference' ||
    props.workflow === 'flux-addon'
      ? null
      : experimentForSubmission(props.experiment, props.form)
  const candidate = {
    ...JSON.parse(JSON.stringify(props.form)),
    request_id: crypto.randomUUID(),
    ...(props.workflow === 'control'
      ? {
          [controlPendingMarker]:
            'control_kind' in props.form && props.form.control_kind
              ? structureWorkflowId
              : controlEdgeWorkflowId,
        }
      : {}),
    ...(props.workflow === 'reference' ? { [referencePendingMarker]: referenceWorkflowId } : {}),
    ...(props.workflow === 'inpaint'
      ? {
          [inpaintPendingMarker]:
            'inpaint_model' in props.form && props.form.inpaint_model
              ? fooocusWorkflowId
              : inpaintFeatherWorkflowId,
        }
      : {}),
    ...(experiment ? { experiment } : {}),
  }
  // A failed local save must never make an unpersisted request dispatchable.
  localStorage.setItem(pendingKey, JSON.stringify(candidate))
  pending.value = candidate
  return candidate
}
function frozenSubmissionDescriptor(frozen: Record<string, unknown>) {
  if (props.workflow === 'flux-addon') return fluxExtensionSubmission(frozen)
  // Versioned adapters choose the original endpoint from the frozen marker.
  if (props.workflow === 'control') return controlSubmission(frozen)
  if (props.workflow === 'reference') return referenceSubmission(frozen)
  if (props.workflow === 'inpaint') return inpaintSubmission(frozen)
  return { path: props.workflow === 'flux' ? '/api/flux/generate' : '/api/generate', body: frozen }
}
function clearConfirmedSubmission() {
  localStorage.removeItem(pendingKey)
  pending.value = null
}
async function generate() {
  if (busy.value || props.disabled) return
  if (!pending.value && (props.blockedReason || hasFieldProblems.value)) return
  busy.value = true
  error.value = ''
  try {
    const frozen = pending.value || freezeCurrentSubmission()
    await submitOnce(frozenSubmissionDescriptor(frozen), clearConfirmedSubmission)
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '提交失敗'
    if (e instanceof ApiError && e.requestId) error.value += `（平台請求 ID：${e.requestId}）`
    if (pending.value) error.value += '。請保留原請求 ID 並使用下方恢復按鈕。'
    await load().catch(() => {})
  } finally {
    busy.value = false
  }
}
async function refresh() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await load()
    const failures: string[] = []
    for (const job of jobs.value.filter((j) => !terminal(j))) {
      try {
        await request(`jobs/${job.id}/refresh`, 'POST')
      } catch (e) {
        failures.push(`${job.id.slice(0, 8)}：${e instanceof Error ? e.message : '查詢失敗'}`)
      }
    }
    await load()
    error.value =
      failures.slice(0, 3).join('；') +
      (failures.length > 3 ? `；另有 ${failures.length - 3} 筆查詢失敗` : '')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '查詢失敗'
  } finally {
    busy.value = false
  }
}
async function cancel(job: Job) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  cancelChoice.value = null
  try {
    await request(`jobs/${job.id}/cancel`, 'POST')
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '無法確認取消結果'
    await load().catch(() => {})
  } finally {
    busy.value = false
  }
}
async function stop(job: Job) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  stopChoice.value = null
  try {
    await request(`jobs/${job.id}/stop`, 'POST')
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '無法確認停止結果'
    await load().catch(() => {})
  } finally {
    busy.value = false
  }
}
const timer = window.setInterval(() => {
  if (
    visible.value &&
    jobs.value.some((j) => !terminal(j) && connections.value[j.id]?.state !== 'connected')
  )
    void refresh()
}, 15000)
onBeforeUnmount(() => window.clearInterval(timer))
</script>
<template>
  <article class="panel generation-history"
    ><Teleport defer :to="submitTarget || 'body'" :disabled="!submitTarget"
      ><div class="generation-submit"
        ><p class="submission-state" role="status" aria-label="提交能力狀態">{{
          submissionAvailability
        }}</p>
        <div class="preflight-feedback">
          <div
            v-if="displayBlockers.length"
            class="notice warning preflight-blockers"
            aria-label="流程與環境阻擋"
            ><strong>需先處理</strong
            ><ul
              ><li v-for="(item, index) in displayBlockers" :key="index"
                >{{ item.message }}
                <a v-if="item.action === 'settings'" href="#/settings">前往引擎設定</a
                ><a v-if="item.action === 'models'" href="#/models">前往模型與元件</a
                ><template v-if="item.action === 'refresh'"
                  ><a href="#/settings">檢查引擎連線</a>
                  <button
                    class="text-button"
                    :disabled="busy || disabled"
                    @click="emit('refreshOptions')"
                    >更新引擎選項</button
                  ></template
                ><span
                  v-if="!item.action && /引擎|ComfyUI|連線|元件/.test(item.message)"
                  class="preflight-links"
                  ><a href="#/settings">檢查引擎連線</a><a href="#/models">檢查模型與元件</a></span
                ></li
              ></ul
            ></div
          >
          <div v-if="hasFieldProblems" class="preflight-fields" aria-label="需修正欄位"
            ><p>請修正 {{ Object.keys(fieldProblems || {}).length }} 個欄位：</p
            ><ul
              ><li v-for="(message, key) in fieldProblems" :key="key"
                ><button
                  type="button"
                  class="text-button"
                  @click="focusPreflightField(submitTarget, String(key))"
                  >{{ fieldLabels[key] || key }}：{{ message }}</button
                ></li
              ></ul
            ></div
          >
          <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
          <p v-if="pending" class="notice warning"
            >尚有未確認的提交
            {{
              pending.request_id
            }}。恢復時使用原始參數，重複請求不會再次入列。請先確認原提交，再載入失敗任務的設定。</p
          >
        </div>
        <button
          type="button"
          class="primary"
          :disabled="
            busy || disabled || (!pending && (missingModel || !!blockedReason || hasFieldProblems))
          "
          @click="generate"
          >{{ busy ? '處理中…' : pending ? '恢復原提交請求' : '生成圖片' }}</button
        ></div
      ></Teleport
    >
    <div class="generation-statusbar"
      ><div
        ><strong>{{ jobs[0] ? labels[jobs[0].status] || jobs[0].status : '尚未開始' }}</strong
        ><p>{{
          jobs[0]?.progress
            ? '目前節點 ' +
              jobs[0].progress.node +
              ' · ' +
              (jobs[0].progress.percent ?? '執行中') +
              '%'
            : jobs[0]
              ? '最近任務的狀態；結果與匯入請查看任務資訊。'
              : '按下「生成」後，進度顯示在這裡。'
        }}</p></div
      ><label v-if="previewStage && jobs.length" class="stage-job-choice"
        >舞台任務<select v-model="previewId"
          ><option value="">最近任務</option
          ><option v-for="job in jobs" :key="job.id" :value="job.id"
            >{{ job.id.slice(0, 8) }} · {{ labels[job.status] || job.status }}</option
          ></select
        ></label
      ><button class="secondary" type="button" @click="historyOpen = !historyOpen"
        >任務與歷史資訊</button
      ></div
    >
    <details
      class="generation-records"
      :open="historyOpen"
      @toggle="historyOpen = ($event.target as HTMLDetailsElement).open"
      ><summary>生成任務與歷史紀錄</summary><h2>生成任務</h2>
      <WorkflowFormatSupport
        v-if="workflow === 'inpaint' || workflow === 'control' || workflow === 'reference'"
        :family="workflow"
      />

      <details class="footnote"
        ><summary>能力與實機驗證範圍</summary
        ><p
          >{{
            workflow === 'flux'
              ? 'FLUX 已完成文件所列固定 512 配置實測。'
              : '此流程已有程式接入；既有實測限文件記錄的硬體、模型與參數。'
          }}目前表單與清單預檢不驗證實際權重
          hash、可用記憶體或生成品質；未知資訊不當作已通過。模型來源／版本可在模型庫查看，任務保存當次快照。</p
        ></details
      >
      <p v-if="checkpointForm" class="footnote"
        >Checkpoint
        {{
          workflow === 'reference'
            ? '畫風／角色外觀參考'
            : workflow === 'control'
              ? 'Canny 結構參考'
              : workflow === 'inpaint'
                ? '局部編輯'
                : imageMode
                  ? '圖生圖'
                  : '文生圖'
        }}
        · {{ form.steps }} steps · {{ checkpointForm.sampler_name }} /
        {{ checkpointForm.scheduler }} · CFG {{ checkpointForm.cfg }} · denoise
        {{ checkpointForm.denoise }} · 每次 1 張。工作流程與精確 seed 會保存到本機。</p
      >
      <p v-else class="footnote"
        >FLUX.1 [schnell] · {{ form.steps }} steps · Euler / simple · CFG 1 · 每次 1
        張。完整流程與四元件快照會保存到本機；目前表單、元件檔案與引擎未自動驗證。</p
      >
      <p v-if="!imageMode && checkpointForm?.reference_ids.length" class="notice warning"
        >文生圖不使用參考素材，請先取消選取，或切換圖生圖流程。</p
      >
      <p v-else-if="checkpointForm && !checkpointForm.checkpoint" class="notice"
        >請先安裝並同步 checkpoint，再選擇模型。</p
      >

      <p v-if="pending?.experiment" class="footnote"
        >恢復原請求會保留原比較組關聯與設定，不使用現在的表單或比較預覽。</p
      >

      <button type="button" class="secondary" :disabled="busy" @click="refresh"
        >更新任務狀態</button
      >
      <button
        v-if="jobs.some((j) => !terminal(j))"
        type="button"
        class="secondary"
        :disabled="busy"
        @click="reconnect"
        >重新連線進度</button
      >
      <p v-if="jobs.some((j) => !terminal(j))" class="footnote"
        >即時監聽最近 4
        個未完成任務。離線時保留最後進度並低頻查詢；切換頁面或隱藏分頁會停止監聽。</p
      >
      <p v-if="!jobs.length" class="footnote"
        >尚無任務。生成結果暫存於 ComfyUI output，平台保留歷史 JSON。</p
      >
      <button v-if="nextCursor" class="secondary" :disabled="busy" @click="older"
        >載入較早任務</button
      >
      <div v-for="job in jobs" :key="job.id" class="job">
        <button
          v-if="!expanded.includes(job.id)"
          class="secondary"
          :disabled="!!detailBusy"
          @click="detail(job)"
          >載入任務詳情</button
        >
        <strong>{{ labels[job.status] || job.status }}</strong> · {{ job.checkpoint }}
        <p class="footnote">{{ new Date(job.created_at).toLocaleString() }} · {{ job.id }}</p>
        <p v-if="job.workflow_id === imageWorkflowId" class="footnote"
          >單張圖生圖 · 原素材與前處理已凍結。</p
        >
        <p v-if="isInpaintWorkflow(job.workflow_id)" class="footnote"
          >局部編輯 · 原圖與遮罩已凍結；白色編輯、黑色保留。</p
        >
        <p v-if="isControlWorkflow(job.workflow_id)" class="footnote"
          >Canny 結構參考 · 空 latent；控制模型與前處理已凍結。</p
        >
        <p v-if="job.workflow_id === referenceWorkflowId" class="footnote"
          >畫風／角色外觀參考 · 單張來源、224 方圖前處理與元件已凍結；不代表身份重現。</p
        >
        <StructureOutput
          v-if="job.workflow_id === structureWorkflowId && job.status === 'completed'"
          :job-id="job.id"
        />
        <ControlEdgePreview
          v-if="job.workflow_id === controlEdgeWorkflowId && job.status === 'completed'"
          :job-id="job.id"
        />
        <p
          v-else-if="
            job.workflow_id !== structureWorkflowId &&
            isControlWorkflow(job.workflow_id) &&
            job.status === 'completed'
          "
          class="footnote"
          >舊版 v1 沒有保存同次邊緣輸出，不會重新計算歷史圖。</p
        >
        <ExperimentSnapshot :item="job.experiment_context" />
        <LoraSnapshot
          v-if="checkpointForm || workflow === 'flux-addon'"
          :items="job.lora_metadata"
        />
        <ControlSnapshot
          v-if="isControlWorkflow(job.workflow_id)"
          :items="job.component_metadata"
        /><ReferenceComponentsSnapshot
          v-else-if="job.workflow_id === referenceWorkflowId"
          :items="job.component_metadata"
        /><ComponentSnapshot v-else :items="job.component_metadata" /><JobMeasurements
          :item="job.measurements"
        />
        <ReferenceSnapshot
          :items="job.reference_metadata"
          :job-id="job.id"
          :processed-ready="
            !!job.input_upload || !!job.input_uploads?.length || job.status === 'completed'
          "
        />
        <details v-if="job.preflight_warnings?.length"
          ><summary>提交時檢查提示（原紀錄）</summary
          ><p class="footnote">以下為提交當時的提示，不代表目前狀態或後續實測結果。</p
          ><p v-for="warning in job.preflight_warnings" :key="warning" class="footnote">{{
            warning
          }}</p></details
        >
        <section
          v-if="job.status === 'failed' && job.failure_info"
          class="failure-info"
          aria-label="任務失敗說明"
        >
          <h3>{{ job.failure_info.title }}</h3
          ><p>{{ job.failure_info.message }}</p>
          <ul v-if="job.failure_info.suggestions.length"
            ><li v-for="(suggestion, index) in job.failure_info.suggestions" :key="index">{{
              suggestion
            }}</li></ul
          >
          <details
            v-if="
              job.failure_info.node_id ||
              job.failure_info.node_type ||
              job.failure_info.exception_type
            "
            ><summary>技術識別資料</summary
            ><dl>
              <template v-if="job.failure_info.node_id"
                ><dt>節點 ID</dt><dd>{{ job.failure_info.node_id }}</dd></template
              >
              <template v-if="job.failure_info.node_type"
                ><dt>節點類型</dt><dd>{{ job.failure_info.node_type }}</dd></template
              >
              <template v-if="job.failure_info.exception_type"
                ><dt>錯誤類型</dt><dd>{{ job.failure_info.exception_type }}</dd></template
              >
            </dl></details
          >
        </section>
        <p v-else-if="job.error" role="status">{{ job.error }}</p>
        <div v-if="job.progress" class="node-progress">
          <p class="footnote"
            >目前節點 {{ job.progress.node }} ·
            {{
              job.progress.percent == null
                ? '正在執行'
                : `${job.progress.percent}%（${job.progress.current} / ${job.progress.max}）`
            }}</p
          >
          <progress
            v-if="job.progress.percent != null"
            :value="job.progress.percent"
            max="100"
            :aria-label="`任務 ${job.id} 目前節點進度`"
          ></progress>
          <p class="footnote"
            >進度更新：{{ new Date(job.progress.updated_at).toLocaleTimeString() }}。{{
              terminal(job)
                ? '這是最後記錄的節點進度，任務結果見上方狀態。'
                : '節點完成後仍需等待引擎確認整個任務。'
            }}</p
          >
        </div>
        <p v-if="!terminal(job)" class="footnote" role="status"
          >{{ connections[job.id] ? connectionLabels[connections[job.id]!.state] : '使用狀態查詢'
          }}<template v-if="connections[job.id]?.message">
            · {{ connections[job.id]!.message }}</template
          ><template v-if="connections[job.id]?.state !== 'connected' && job.progress">
            · 上次進度可能已過期</template
          ></p
        >
        <template v-if="job.status === 'queued'"
          ><button
            v-if="cancelChoice !== job.id"
            type="button"
            class="secondary"
            :disabled="busy"
            @click="cancelChoice = job.id"
            >取消排隊</button
          ><div v-else class="notice"
            ><p>只移除這個任務的排隊項目。若它已開始執行，平台會保留任務並提示最新狀態。</p
            ><button type="button" class="secondary" :disabled="busy" @click="cancelChoice = null"
              >保留任務</button
            ><button type="button" class="secondary" :disabled="busy" @click="cancel(job)"
              >確認取消此任務</button
            ></div
          ></template
        >
        <button
          v-if="['cancelling', 'cancel_unknown'].includes(job.status)"
          type="button"
          class="secondary"
          :disabled="busy"
          @click="cancel(job)"
          >確認取消結果</button
        >
        <template v-if="job.status === 'running'"
          ><button
            v-if="stopChoice !== job.id"
            type="button"
            class="secondary"
            :disabled="busy"
            @click="stopChoice = job.id"
            >停止此任務</button
          ><div v-else class="notice warning"
            ><p
              >只停止這個任務。需原引擎具備已驗證的指定任務停止能力；若已完成會保留結果，停止請求仍需歷史確認。</p
            ><button type="button" class="secondary" :disabled="busy" @click="stopChoice = null"
              >繼續生成</button
            ><button type="button" class="secondary" :disabled="busy" @click="stop(job)"
              >確認停止此任務</button
            ></div
          ></template
        >
        <button
          v-if="['stopping', 'stop_unknown'].includes(job.status)"
          type="button"
          class="secondary"
          :disabled="busy"
          @click="stop(job)"
          >確認停止結果</button
        >
        <template
          v-if="
            job.status === 'failed' ||
            ((workflow === 'flux' ||
              workflow === 'flux-addon' ||
              job.workflow_id === imageWorkflowId ||
              isInpaintWorkflow(job.workflow_id) ||
              isControlWorkflow(job.workflow_id) ||
              job.workflow_id === referenceWorkflowId) &&
              terminal(job))
          "
          ><button
            type="button"
            class="secondary"
            :aria-label="`載入原設定並調整：${job.id}`"
            :disabled="busy || disabled || !!pending"
            @click="emit('restoreJob', job.id)"
            >載入原設定並調整</button
          ><p class="footnote">載入後可手動調整，再按「生成圖片」建立新任務。</p></template
        >
        <button v-if="job.status === 'completed'" class="secondary" @click="emit('gallery', job.id)"
          >前往作品庫匯入圖片 →</button
        >
        <a :href="`/api/jobs/${job.id}/workflow`">下載完整工作流程</a> ·
        <a :href="`/api/jobs/${job.id}`" target="_blank" rel="noopener">任務／歷史 JSON</a>
      </div>
    </details></article
  >
</template>
<style scoped>
button {
  margin: 4px 8px 10px 0;
}
.job {
  border-top: 1px solid #35403a;
  padding: 15px 0;
  font-size: 12px;
  overflow-wrap: anywhere;
}
.job a {
  color: #c5dfba;
}
.node-progress {
  margin: 12px 0;
}
progress {
  width: 100%;
  height: 8px;
  accent-color: #c5dfba;
}
.failure-info {
  background: #2c2720;
  border: 1px solid #625342;
  border-radius: 8px;
  padding: 14px;
  margin: 12px 0;
}
.failure-info h3 {
  font-size: 13px;
  margin: 0;
  color: #ebc4a1;
}
.failure-info p {
  line-height: 1.7;
}
.failure-info ul {
  padding-left: 20px;
  line-height: 1.8;
}
.failure-info details {
  margin-top: 12px;
}
.failure-info summary {
  cursor: pointer;
  color: #c8bba9;
}
.failure-info dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 12px;
  font-size: 11px;
}
.failure-info dt {
  color: #b6a48d;
}
.failure-info dd {
  margin: 0;
  font-family: monospace;
}
</style>
