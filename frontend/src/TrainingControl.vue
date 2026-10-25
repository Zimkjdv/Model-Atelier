<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from './apiClient'
import { createRequestScope } from './requestScope'
import { useUnsavedChanges } from './unsavedChanges'

type RequestRecord = {
  request_id: string
  status: string
  run_id: string | null
  error?: string
  evaluation_path?: string
  evaluation?: { plans: unknown[]; generation_started: boolean }
}
type Run = {
  run_id: string
  status: string
  resources_released: boolean
  manifest_sha256: string
  configuration: Record<string, any>
  dataset: Record<string, unknown>
  base: Record<string, unknown>
  environment: Record<string, unknown>
  state: Record<string, any>
  resume: unknown
  checkpoints: { id: string; step: number }[]
  resources: unknown
  artifacts: unknown
  log_tail: string
  start_requested: boolean
  dispatch_error?: string
}
type Listing = {
  available: boolean
  requests: RequestRecord[]
  runs: Pick<Run, 'run_id' | 'status' | 'configuration'>[]
  exports: { request_id: string; dataset_label: string; revision: number; kind: string }[]
}
const emit = defineEmits<{ dirty: [value: boolean] }>()
const listing = ref<Listing | null>(null),
  current = ref<Run | null>(null),
  requestRecord = ref<RequestRecord | null>(null)
const busy = ref(false),
  checking = ref(false),
  refreshing = ref(false),
  error = ref(''),
  message = ref(''),
  requestId = ref(''),
  imported = ref(''),
  checkpoint = ref('')
const environment = ref<{ ready: boolean; issues: string[] } | null>(null)
const form = ref({
  export_id: '',
  label: '',
  purpose: 'development-training',
  gpu_index: 0,
  resolution: 1024,
  rank: 4,
  learning_rate: 0.0001,
  max_steps: 100,
  save_every_steps: 100,
  seed: 42,
})
const saved = ref(JSON.stringify(form.value)),
  dirty = computed(() => saved.value !== JSON.stringify(form.value))
const protectedState = computed(() => dirty.value || busy.value)
useUnsavedChanges(protectedState)
watch(protectedState, (v) => emit('dirty', v), { immediate: true })
const scope = createRequestScope(),
  runScope = createRequestScope(),
  requestScope = createRequestScope()
const startPending = ref('')
let alive = true,
  polling = false,
  timer: ReturnType<typeof setInterval> | undefined
const statusNames: Record<string, string> = {
  preparing: '準備中',
  prepared: '已準備，尚未開始',
  starting: '啟動中',
  start_requested: '已要求啟動',
  running: '訓練中',
  stopping: '停止中',
  finishing: '程序收尾中',
  stopped: '已停止',
  completed: '已完成',
  blocked: '啟動被阻擋',
  failed: '失敗',
  interrupted: '已中斷',
  start_unknown: '啟動結果不明',
  unavailable: '原紀錄不可讀',
}
const label = (status: string) => statusNames[status] || status
const resumable = computed(() =>
  (current.value?.checkpoints || []).filter(
    (v) => v.step < (current.value?.configuration.max_steps || 0),
  ),
)
async function refresh() {
  if (refreshing.value) return
  const request = scope.begin()
  refreshing.value = true
  try {
    const result = await api<Listing>('training/control', 'GET', undefined, request.signal)
    if (alive && request.isCurrent()) listing.value = result
  } catch (e) {
    if (alive && request.isCurrent()) error.value = String(e)
  } finally {
    if (alive && request.isCurrent()) refreshing.value = false
  }
}
async function loadRun(id: string) {
  const request = runScope.begin()
  const result = await api<Run>('training/runs/' + id, 'GET', undefined, request.signal)
  if (alive && request.isCurrent()) {
    if (current.value?.run_id !== id) artifact.value = null
    current.value = result
    checkpoint.value =
      result.checkpoints.filter((v) => v.step < result.configuration.max_steps)[0]?.id || ''
    if (startPending.value === id) startPending.value = ''
  }
}
async function action(fn: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await fn()
  } catch (e) {
    if (alive) error.value = String(e)
  } finally {
    if (alive) busy.value = false
  }
}
function remember(id: string) {
  requestId.value = id
  try {
    localStorage.setItem('atelier-training-request', id)
  } catch {
    message.value = '瀏覽器無法保存請求索引；請保留畫面 UUID，仍可從請求清單查回。'
  }
}
function selectRequest(id: string) {
  remember(id)
  void action(() => queryRequest())
}
async function queryRequest(id = requestId.value) {
  if (!id) return
  const request = requestScope.begin()
  const result = await api<RequestRecord>(
    'training/requests/' + id,
    'GET',
    undefined,
    request.signal,
  )
  if (alive && request.isCurrent() && id === requestId.value) requestRecord.value = result
}
async function prepare(kind: 'new' | 'resume' | 'evaluation') {
  await action(async () => {
    const id = crypto.randomUUID()
    remember(id)
    let path = 'training/requests',
      body: Record<string, unknown> = { ...form.value, request_id: id }
    if (kind === 'resume') {
      path = 'training/resume-requests'
      body = { request_id: id, resume_run_id: current.value!.run_id, checkpoint: checkpoint.value }
    }
    if (kind === 'evaluation') {
      path = 'training/evaluation-requests'
      body = { request_id: id, run_id: current.value!.run_id }
    }
    const result = await api<RequestRecord>(path, 'POST', body)
    if (alive) {
      requestRecord.value = result
      if (kind === 'new') saved.value = JSON.stringify(form.value)
      await refresh()
    }
  })
}
function newRequest() {
  remember('')
  requestRecord.value = null
  message.value = '下一次明確操作將建立新 UUID，舊請求仍保留。'
}
async function checkEnvironment() {
  checking.value = true
  error.value = ''
  try {
    const value = await api<{ ready: boolean; issues: string[] }>('training/runtime/check', 'POST')
    if (alive) environment.value = value
  } catch (e) {
    if (alive) error.value = String(e)
  } finally {
    if (alive) checking.value = false
  }
}
async function runAction(operation: 'start' | 'stop' | 'artifact' | 'publish') {
  if (!current.value) return
  const id = current.value.run_id
  await action(async () => {
    if (operation === 'start') startPending.value = id
    const result = await api<any>(`training/runs/${id}/${operation}`, 'POST')
    if (alive) {
      message.value =
        operation === 'artifact'
          ? '產物身分已驗證並安裝，尚未認列畫風／角色品質。'
          : operation === 'publish'
            ? '已同步原生模型庫與產物來源。'
            : '已送出明確要求；狀態與資源釋放仍以原 run 查詢為準。'
      if (operation === 'artifact') artifact.value = result
      await loadRun(id)
      await refresh()
    }
  })
}
const artifact = ref<unknown>(null)
async function importExisting() {
  await action(async () => {
    const result = await api<Run>('training/runs/import', 'POST', { run_id: imported.value })
    if (alive) {
      await loadRun(result.run_id)
      await refresh()
    }
  })
}
async function poll() {
  if (!alive || busy.value || refreshing.value || polling) return
  polling = true
  try {
    if (requestId.value && requestRecord.value?.status === 'preparing') await queryRequest()
    if (
      current.value &&
      (!current.value.resources_released ||
        startPending.value === current.value.run_id ||
        ['starting', 'running', 'stopping'].includes(current.value.status))
    ) {
      const id = current.value.run_id,
        request = runScope.begin(),
        result = await api<Run>('training/runs/' + id, 'GET', undefined, request.signal)
      if (alive && request.isCurrent() && current.value?.run_id === id) {
        current.value = result
        startPending.value = ''
      }
    }
  } catch (e) {
    if (alive && !(e instanceof Error && e.name === 'AbortError'))
      error.value = '原狀態暫不可讀，保留上次資料；請明確查回。' + String(e)
  } finally {
    polling = false
  }
}
onMounted(async () => {
  await refresh()
  try {
    const id = localStorage.getItem('atelier-training-request') || ''
    if (/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(id)) {
      requestId.value = id
      await queryRequest()
    }
  } catch {
    /* Recovery remains available through the durable request list. */
  }
  if (alive)
    timer = setInterval(() => {
      if (document.visibilityState === 'visible') void poll()
    }, 2000)
})
onUnmounted(() => {
  alive = false
  scope.dispose()
  runScope.dispose()
  requestScope.dispose()
  clearInterval(timer)
  emit('dirty', false)
})
</script>

<template>
  <div class="training-control">
    <article class="panel"
      ><h2>本機訓練執行</h2
      ><p>準備 run、啟動訓練與續訓是分開的操作；離開頁面不會停止已啟動的 worker。</p
      ><p v-if="error" class="notice warning" role="alert">{{ error }}</p
      ><p role="status">{{ message }}</p>
      <p v-if="listing && !listing.available"
        >僅支援 Windows 原生訓練環境；容器與其他 OS 不提供啟動操作。</p
      >
      <template v-if="listing?.available"
        ><div class="training-actions"
          ><button
            class="secondary"
            type="button"
            :disabled="checking || busy"
            @click="checkEnvironment"
            >{{ checking ? '檢查中…' : '檢查獨立訓練環境' }}</button
          ><button class="secondary" type="button" :disabled="busy || refreshing" @click="refresh"
            >更新訓練清單</button
          ></div
        ><p v-if="environment" role="status">{{
          environment.ready ? '獨立環境檢查通過；不代表已開始訓練' : '訓練環境尚未就緒'
        }}</p
        ><ul v-if="environment"
          ><li v-for="issue in environment.issues" :key="issue">{{ issue }}</li></ul
        ></template
      >
    </article>
    <template v-if="listing?.available">
      <form class="panel" @submit.prevent="prepare('new')"
        ><h2>建立凍結訓練設定</h2
        ><p class="footnote"
          >固定基底為 Animagine XL 4.0 Opt；只接受 T05
          已封存資料包。準備階段會驗證環境、資料與實際基底 hash，不開始訓練。</p
        ><fieldset :disabled="busy || !!requestId"
          ><legend>新 run 設定</legend
          ><div class="training-fields">
            <label
              >已封存資料包<select v-model="form.export_id" required aria-label="已封存資料包"
                ><option value="">請選擇</option
                ><option
                  v-for="item in listing.exports"
                  :key="item.request_id"
                  :value="item.request_id"
                  >{{ item.dataset_label }} · {{ item.kind }} · 修訂 {{ item.revision }} ·
                  {{ item.request_id.slice(0, 8) }}</option
                ></select
              ></label
            >
            <label>訓練名稱<input v-model="form.label" required maxlength="120" /></label
            ><label
              >用途<select v-model="form.purpose" aria-label="用途"
                ><option value="development-training">開發試訓；品質未評估</option
                ><option value="technical-smoke">自製技術測試；不作畫風品質證據</option></select
              ></label
            >
            <label
              >訓練尺寸<select v-model.number="form.resolution" aria-label="訓練尺寸"
                ><option :value="512">512</option
                ><option :value="1024">1024</option></select
              ></label
            ><label
              >LoRA rank<select v-model.number="form.rank" aria-label="LoRA rank"
                ><option v-for="rank in [4, 8, 16]" :key="rank" :value="rank">{{
                  rank
                }}</option></select
              ></label
            >
            <label
              >總更新步數<input
                v-model.number="form.max_steps"
                type="number"
                min="1"
                max="10000"
                required /></label
            ><label
              >保存間隔（步）<input
                v-model.number="form.save_every_steps"
                type="number"
                min="1"
                max="10000"
                required /></label
            ><label
              >Learning rate<input
                v-model.number="form.learning_rate"
                type="number"
                min="0.00000001"
                max="0.01"
                step="any"
                required /></label
            ><label
              >訓練 seed<input
                v-model.number="form.seed"
                type="number"
                min="0"
                max="4294967295"
                required /></label
            ><label
              >NVIDIA 裝置 index<input
                v-model.number="form.gpu_index"
                type="number"
                min="0"
                max="15"
                required
            /></label> </div
          ><button type="submit" class="primary" :disabled="!form.export_id || !form.label"
            >準備新 run（不開始訓練）</button
          ></fieldset
        ><p v-if="!listing.exports.length">尚無完成的資料包，先到資料審查完成標註並匯出。</p></form
      >
      <article class="panel"
        ><h2>原訓練請求</h2><p class="footnote">回應不明時只查回原 UUID，不自動重做準備或啟動。</p
        ><p>請求 UUID：{{ requestId || '尚未建立' }}</p
        ><div class="training-actions"
          ><button
            class="secondary"
            type="button"
            :disabled="busy || !requestId"
            @click="action(() => queryRequest())"
            >查回原訓練請求</button
          ><button
            class="secondary"
            type="button"
            :disabled="busy || requestRecord?.status === 'preparing'"
            @click="newRequest"
            >準備另一個請求</button
          ></div
        >
        <template v-if="requestRecord"
          ><p role="status">請求狀態：{{ label(requestRecord.status) }}</p
          ><p v-if="requestRecord.error" role="alert">{{ requestRecord.error }}</p
          ><button
            class="secondary"
            v-if="requestRecord.run_id && requestRecord.status === 'prepared'"
            type="button"
            :disabled="busy"
            @click="action(() => loadRun(requestRecord!.run_id!))"
            >開啟新 run</button
          ><p v-if="requestRecord.evaluation" role="status"
            >已保存 {{ requestRecord.evaluation.plans.length }} 份比較方案，沒有生成圖片。</p
          ><p v-if="requestRecord.evaluation_path">{{ requestRecord.evaluation_path }}</p></template
        >
        <details
          ><summary>已保存的請求 UUID</summary
          ><ul
            ><li v-for="item in listing.requests" :key="item.request_id"
              ><button
                class="secondary"
                type="button"
                :disabled="busy"
                @click="selectRequest(item.request_id)"
                >{{ item.request_id }} · {{ label(item.status) }}</button
              ></li
            ></ul
          ></details
        >
      </article>
      <article class="panel"
        ><h2>原 run 與狀態</h2
        ><form class="training-actions" @submit.prevent="importExisting"
          ><label>既有 CLI run UUID<input v-model="imported" required maxlength="36" /></label
          ><button class="secondary" type="submit" :disabled="busy"
            >登記既有 run（不啟動）</button
          ></form
        >
        <div class="training-actions"
          ><button
            class="secondary"
            v-for="item in listing.runs"
            :key="item.run_id"
            type="button"
            :disabled="busy"
            @click="action(() => loadRun(item.run_id))"
            >{{ item.configuration.label }} · {{ item.run_id.slice(0, 8) }} ·
            {{ label(item.status) }}</button
          ></div
        >
        <template v-if="current"
          ><h3>{{ current.configuration.label }}</h3
          ><p>Run UUID：{{ current.run_id }}</p
          ><p role="status"
            >狀態：{{ label(current.status) }} ·
            {{ current.resources_released ? '程序與租約已釋放' : '程序或租約尚未釋放' }}</p
          ><p
            >更新步數：{{
              current.state?.steps_completed ?? current.state?.last_checkpoint_step ?? '尚未回報'
            }}
            / {{ current.configuration.max_steps }}</p
          ><p v-if="current.state?.message || current.dispatch_error" role="alert">{{
            current.state?.message || current.dispatch_error
          }}</p
          ><p class="footnote"
            >每 2 秒查閱活躍 run；失敗保留上次資料。開始前先完成目前 GPU 工作、停止受管理 ComfyUI
            8188 與容器平台。程式不結束其他服務或軟體。</p
          >
          <div class="training-actions"
            ><button
              type="button"
              class="primary"
              :disabled="
                busy ||
                current.status !== 'prepared' ||
                !current.resources_released ||
                current.start_requested ||
                startPending === current.run_id
              "
              @click="runAction('start')"
              >開始此 run 的訓練</button
            ><button
              class="secondary"
              type="button"
              :disabled="busy || current.resources_released"
              @click="runAction('stop')"
              >要求停止此 run</button
            ><button
              class="secondary"
              type="button"
              :disabled="busy"
              @click="action(() => loadRun(current!.run_id))"
              >查回原 run 狀態</button
            ></div
          >
          <p v-if="current.status === 'start_unknown'" class="notice warning"
            >啟動結果不明，不重送啟動。保留原 run 與日誌，確認 worker 狀態後明確準備新嘗試。</p
          >
          <div class="training-actions"
            ><label
              >完整 checkpoint<select v-model="checkpoint" aria-label="完整 checkpoint"
                ><option value="">請選擇</option
                ><option v-for="item in resumable" :key="item.id" :value="item.id">{{
                  item.id
                }}</option></select
              ></label
            ><button
              class="secondary"
              type="button"
              :disabled="busy || !current.resources_released || !checkpoint || !!requestId"
              @click="prepare('resume')"
              >以新 UUID 準備續訓（不開始）</button
            ></div
          >
          <p class="footnote"
            >續訓保留原設定與完整狀態，不增加總步數；需先按「準備另一個請求」再建立新請求。準備完成後仍要明確開始。</p
          >
          <details
            ><summary>凍結設定與來源</summary
            ><pre>{{
              JSON.stringify(
                {
                  manifest_sha256: current.manifest_sha256,
                  configuration: current.configuration,
                  dataset: current.dataset,
                  base: current.base,
                  environment: current.environment,
                  resume: current.resume,
                },
                null,
                2,
              )
            }}</pre>
          </details>
          <details
            ><summary>資源紀錄（未知保持未知）</summary
            ><p>PyTorch allocator、程序 RAM 與整卡取樣是不同來源，整卡數字包含其他軟體。</p
            ><pre>{{ JSON.stringify(current.resources, null, 2) }}</pre></details
          ><details
            ><summary>原 worker 日誌（最後 64 KiB）</summary
            ><pre>{{ current.log_tail || '尚未寫入日誌' }}</pre>
          </details>
          <h3>訓練產物與固定比較</h3
          ><p class="footnote"
            >只接受完成且資源已釋放的
            run。安裝不等於模型庫已同步，登記不代表畫風／角色品質通過；比較方案只保存設定，不生成。</p
          ><div class="training-actions"
            ><button
              class="secondary"
              type="button"
              :disabled="busy || current.status !== 'completed' || !current.resources_released"
              @click="runAction('artifact')"
              >驗證並安裝 LoRA</button
            ><button
              class="secondary"
              type="button"
              :disabled="busy || current.status !== 'completed' || !current.resources_released"
              @click="runAction('publish')"
              >同步模型庫與來源登記</button
            ><button
              class="secondary"
              type="button"
              :disabled="
                busy || current.status !== 'completed' || !current.resources_released || !!requestId
              "
              @click="prepare('evaluation')"
              >建立固定比較方案（不生成）</button
            ></div
          ><p class="footnote"
            >同步需自行恢復原生 ComfyUI，並在設定選擇 http://127.0.0.1:8188；比較前確認基底與 LoRA
            登記。作者最終評估仍需獨立保留圖。</p
          ><details
            ><summary>產物 receipt／安裝結果</summary
            ><pre>{{ JSON.stringify(artifact || current.artifacts, null, 2) }}</pre>
          </details>
        </template>
      </article>
    </template>
  </div>
</template>

<style scoped>
.training-control {
  display: grid;
  gap: 20px;
  min-width: 0;
}
.training-control p,
.training-control li {
  overflow-wrap: anywhere;
}
.training-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin: 16px 0;
}
.training-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.training-control fieldset {
  min-width: 0;
  border: 1px solid #3a443e;
  border-radius: 8px;
  padding: 16px;
}
.training-control label {
  display: grid;
  gap: 8px;
  font-size: 12px;
  min-width: 0;
}
.training-control input,
.training-control select {
  width: 100%;
  box-sizing: border-box;
  min-width: 0;
  min-height: 40px;
}
.training-control pre {
  max-height: 420px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 11px;
}
.training-control details {
  margin: 16px 0;
}
.training-control button {
  overflow-wrap: anywhere;
  max-width: 100%;
}
@media (max-width: 650px) {
  .training-fields {
    grid-template-columns: 1fr;
  }
}
</style>
