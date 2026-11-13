<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, ref, useId, watch } from 'vue'
import { api, apiJson } from './apiClient'
import {
  canonicalExperimentSettings,
  type ExperimentLoad,
  type ExperimentResults,
  type ExperimentVariant,
} from './experimentSettings'
import { createRequestScope } from './requestScope'
import {
  selectionFor,
  specializedBody,
  specializedWorkflow,
  variantDocument,
  type SpecializedDocument,
  type SpecializedDraft,
  type SpecializedFamily,
  type SpecializedForm,
  type SpecializedPlan,
  type SpecializedPlanRecord,
  type SpecializedPlanSummary,
  type SpecializedPreview,
} from './specializedSettings'

const props = defineProps<{
  family: SpecializedFamily
  workflowId: string
  form: SpecializedForm
  disabled: boolean
  experiment: ExperimentLoad | null
  apply: (value: SpecializedDocument, saved: boolean, experiment?: ExperimentLoad) => boolean
  saved: () => void
}>()
const emit = defineEmits<{ detach: []; gallery: [jobId: string] }>()
const uid = useId()
const base = 'specialized/'
const drafts = ref<SpecializedDraft[]>([])
const plans = ref<SpecializedPlanSummary[]>([])
const draftId = ref('')
const planId = ref('')
const currentDraft = ref<SpecializedDraft | null>(null)
const loadedDocument = ref<SpecializedDocument | null>(null)
const importPreview = ref<SpecializedPreview | null>(null)
const differences = computed(() => {
  if (!importPreview.value) return []
  const before = specializedBody(props.form, props.workflowId) as unknown as Record<string, unknown>
  return Object.entries(importPreview.value.document.settings).filter(
    ([key, value]) =>
      canonicalExperimentSettings(before[key]) !== canonicalExperimentSettings(value),
  )
})
const plan = ref<SpecializedPlanRecord | null>(null)
const preview = ref<SpecializedPlan | null>(null)
const saveId = ref('')
const results = ref<ExperimentResults | null>(null)
const error = ref('')
const status = ref('')
const busy = ref(false)
const axis = ref('seed')
const values = ref('')
const reads = createRequestScope()
const axes = computed(() => {
  const common = [
    ['seed', 'Seed'],
    ['steps', 'Steps'],
    ['cfg', 'CFG'],
  ]
  if ('grow_mask_by' in props.form) {
    common.push(['grow_mask_by', '遮罩擴張'])
    if (props.workflowId !== 'checkpoint-inpaint-v1') common.push(['feather_radius', '羽化半徑'])
    if (!props.form.inpaint_model) common.push(['denoise', '重繪強度'])
  } else if ('control_strength' in props.form) {
    common.push(
      ['control_strength', '控制強度'],
      ['control_start', '控制起點'],
      ['control_end', '控制終點'],
    )
    if (!props.form.control_kind)
      common.push(['canny_low', 'Canny 低閾值'], ['canny_high', 'Canny 高閾值'])
  } else
    common.push(
      ['reference_weight', '參考權重'],
      ['reference_start', '參考起點'],
      ['reference_end', '參考終點'],
    )
  return common
})
const formSignature = computed(() =>
  canonicalExperimentSettings([props.workflowId, specializedBody(props.form, props.workflowId)]),
)
watch(
  formSignature,
  () => {
    preview.value = null
    if (!axes.value.some(([id]) => id === axis.value)) axis.value = 'seed'
  },
  { flush: 'sync' },
)
watch(
  [axis, values],
  () => {
    preview.value = null
  },
  { flush: 'sync' },
)

async function run(action: (signal: AbortSignal) => Promise<void>) {
  if (busy.value) return
  const request = reads.begin()
  busy.value = true
  error.value = ''
  status.value = ''
  try {
    await action(request.signal)
  } catch (cause) {
    if (request.isCurrent()) error.value = cause instanceof Error ? cause.message : '操作失敗'
  } finally {
    if (request.isCurrent()) busy.value = false
  }
}
function active(signal: AbortSignal) {
  return !signal.aborted
}
function post<T>(path: string, value: unknown, signal: AbortSignal, method = 'POST') {
  return api<T>(base + path, method, value, signal)
}
async function refresh(signal: AbortSignal) {
  const [savedDrafts, savedPlans] = await Promise.all([
    apiJson<SpecializedDraft[]>(base + 'drafts?family=' + props.family, { signal }),
    apiJson<SpecializedPlanSummary[]>(base + 'comparisons?family=' + props.family, { signal }),
  ])
  if (!active(signal)) return
  drafts.value = savedDrafts
  plans.value = savedPlans
}
function opening(event: Event) {
  if ((event.currentTarget as HTMLDetailsElement).open) void run(refresh)
}
onActivated(() => {
  if (drafts.value.length || plans.value.length) void run(refresh)
})
onDeactivated(() => {
  reads.cancel()
  busy.value = false
})
onBeforeUnmount(reads.dispose)

function documentOf(record: SpecializedDraft): SpecializedDocument {
  const { id, revision, ...document } = record as SpecializedDraft & {
    created_at?: string
    updated_at?: string
  }
  delete document.created_at
  delete document.updated_at
  return document
}
function snapshot(signal: AbortSignal): Promise<SpecializedDocument> {
  const settings = specializedBody(props.form, props.workflowId)
  const origin = loadedDocument.value
  if (
    origin?.workflow_id === props.workflowId &&
    canonicalExperimentSettings(origin.settings) === canonicalExperimentSettings(settings)
  )
    return Promise.resolve(origin)
  return post('settings/capture', { workflow_id: props.workflowId, settings }, signal)
}
function previewDocument(value: SpecializedDocument, signal: AbortSignal) {
  return post<SpecializedPreview>('settings/import-preview', value, signal)
}
function saveDraft(update: boolean) {
  const original = update ? currentDraft.value : null
  if (props.disabled || (update && !original)) return
  void run(async (signal) => {
    const signature = formSignature.value
    const document = await snapshot(signal)
    if (!active(signal) || props.disabled || signature !== formSignature.value) return
    const saved = await post<SpecializedDraft>(
      original ? 'drafts/' + original.id : 'drafts',
      { document, ...(original ? { revision: original.revision } : {}) },
      signal,
      original ? 'PUT' : 'POST',
    )
    if (!active(signal)) return
    currentDraft.value = saved
    draftId.value = saved.id
    if (signature === formSignature.value) {
      loadedDocument.value = documentOf(saved)
      props.saved()
    }
    await refresh(signal)
    if (active(signal)) status.value = '已保存專用草稿。'
  })
}
function loadDraft() {
  if (props.disabled) return
  void run(async (signal) => {
    const draft = drafts.value.find((row) => row.id === draftId.value)
    if (!draft) return
    const checked = await previewDocument(documentOf(draft), signal)
    if (!active(signal)) return
    if (!checked.loadable) throw new Error(checked.warnings.join(' '))
    if (props.apply(checked.document, true)) {
      currentDraft.value = draft
      loadedDocument.value = checked.document
      status.value = checked.warnings.join(' ') || '已載入專用草稿。'
    }
  })
}
function download(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }),
  )
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function exportSettings() {
  if (props.disabled) return
  void run(async (signal) => {
    const document = await snapshot(signal)
    if (active(signal)) download(document, 'model-atelier-specialized-settings.json')
  })
}
function importFile(event: Event, comparison = false) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || props.disabled) return
  if (comparison) preview.value = null
  else importPreview.value = null
  void run(async (signal) => {
    if (file.size > (comparison ? 1024 : 256) * 1024) throw new Error('設定檔超過大小上限。')
    const value = await apiJson<SpecializedPreview & { plan?: SpecializedPlan }>(
      base + (comparison ? 'comparisons/import-preview' : 'settings/import-preview'),
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: file, signal },
    )
    if (!active(signal)) return
    if (comparison) {
      if (
        value.plan &&
        specializedWorkflow(props.family, value.document.settings, value.document.workflow_id) !==
          value.document.workflow_id
      )
        throw new Error('這份比較方案屬於其他工作台。')
      if (!value.loadable || !value.plan)
        throw new Error(value.warnings.join(' ') || '方案無法載入。')
      preview.value = value.plan
      saveId.value = crypto.randomUUID()
      status.value = value.warnings.join(' ')
    } else importPreview.value = value
  })
}
function applyImport() {
  const value = importPreview.value
  if (!value?.loadable || props.disabled) return
  if (
    specializedWorkflow(props.family, value.document.settings, value.document.workflow_id) !==
    value.document.workflow_id
  ) {
    error.value = '這份設定屬於其他工作台，請在對應的工作台匯入。'
    return
  }
  if (!props.apply(value.document, false)) return
  currentDraft.value = null
  draftId.value = ''
  loadedDocument.value = value.document
  importPreview.value = null
  status.value = '已載入匯入設定。可另存成專用草稿。'
}
function previewPlan() {
  if (props.disabled) return
  void run(async (signal) => {
    const signature = formSignature.value
    const selectedAxis = axis.value
    const entered = values.value
    const items = entered.split(/[,，]/).map((item) => item.trim())
    if (items.length < 2 || items.length > 4 || items.some((item) => !item))
      throw new Error('請輸入 2–4 個以逗號分隔的值。')
    const document = await snapshot(signal)
    const candidate = await post<SpecializedPlan>(
      'comparisons/preview',
      {
        document,
        axis: selectedAxis,
        values: selectedAxis === 'seed' ? items : items.map(Number),
      },
      signal,
    )
    if (
      !active(signal) ||
      signature !== formSignature.value ||
      selectedAxis !== axis.value ||
      entered !== values.value
    )
      return
    preview.value = candidate
    saveId.value = crypto.randomUUID()
  })
}
async function readResults(signal: AbortSignal, record = plan.value) {
  if (!record) return
  const value = await apiJson<ExperimentResults>(base + 'comparisons/' + record.id + '/results', {
    signal,
  })
  if (value.plan_id !== record.id || value.plan_sha256 !== record.plan.plan_sha256)
    throw new Error('結果與目前比較方案不符。')
  if (active(signal)) results.value = value
}
function savePlan() {
  const candidate = preview.value
  if (!candidate || props.disabled) return
  void run(async (signal) => {
    const saved = await post<SpecializedPlanRecord>(
      'comparisons',
      { plan: candidate, request_id: saveId.value },
      signal,
    )
    if (!active(signal)) return
    plan.value = saved
    planId.value = saved.id
    results.value = null
    preview.value = null
    await refresh(signal)
    await readResults(signal, saved)
    if (active(signal)) status.value = '已保存比較方案。請選擇一組後手動生成。'
  })
}
function loadPlan() {
  if (!planId.value) return
  void run(async (signal) => {
    const record = await apiJson<SpecializedPlanRecord>(base + 'comparisons/' + planId.value, {
      signal,
    })
    if (!active(signal)) return
    plan.value = record
    results.value = null
    await readResults(signal, record)
  })
}
function archivePlan() {
  const record = plan.value
  if (!record || props.disabled) return
  void run(async (signal) => {
    const changed = await post<SpecializedPlanRecord>(
      'comparisons/' + record.id,
      {
        revision: record.revision,
        archived: !record.archived,
      },
      signal,
      'PUT',
    )
    if (!active(signal)) return
    plan.value = changed
    await refresh(signal)
  })
}
function applyVariant(variant: ExperimentVariant) {
  const record = plan.value
  if (!record || record.archived || props.disabled) return
  void run(async (signal) => {
    const checked = await previewDocument(variantDocument(record.plan, variant), signal)
    if (!active(signal)) return
    if (!checked.loadable || checked.warnings.length) throw new Error(checked.warnings.join(' '))
    if (
      props.apply(checked.document, false, {
        selection: selectionFor(record, variant),
        plan_title: record.plan.title,
        archived: record.archived,
        settings: variant.settings,
      })
    ) {
      currentDraft.value = null
      draftId.value = ''
      loadedDocument.value = checked.document
      status.value = '已載入比較組，請手動生成。'
    }
  })
}
</script>

<template>
  <details class="specialized-settings" @toggle="opening">
    <summary>專用草稿、設定交換與比較</summary>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <p v-if="status" role="status">{{ status }}</p>
    <p class="footnote">目前流程 {{ workflowId }}</p>
    <fieldset :disabled="busy || disabled">
      <legend>專用草稿</legend>
      <label :for="uid + '-draft'">已保存草稿</label>
      <select :id="uid + '-draft'" v-model="draftId">
        <option value="">選擇草稿</option>
        <option v-for="draft in drafts" :key="draft.id" :value="draft.id"
          >{{ draft.settings.title }} · {{ draft.workflow_id }}</option
        >
      </select>
      <div class="actions">
        <button type="button" :disabled="!draftId" @click="loadDraft">載入專用草稿</button>
        <button type="button" @click="saveDraft(false)">另存專用草稿</button>
        <button type="button" :disabled="!currentDraft" @click="saveDraft(true)"
          >更新目前草稿</button
        >
      </div>
      <p v-if="currentDraft" class="footnote"
        >目前草稿 {{ currentDraft.settings.title }} · 修訂 {{ currentDraft.revision }}</p
      >
    </fieldset>
    <fieldset :disabled="busy || disabled">
      <legend>專用設定交換</legend>
      <div class="actions">
        <button type="button" @click="exportSettings">匯出專用設定 JSON</button>
      </div>
      <label :for="uid + '-import'">匯入專用設定 JSON</label>
      <input
        :id="uid + '-import'"
        type="file"
        accept=".json,application/json"
        @change="importFile($event)"
      />
      <section v-if="importPreview" aria-label="專用匯入預覽">
        <p
          >{{ importPreview.document.workflow_id }} · {{ importPreview.document.settings.title }}</p
        >
        <p class="footnote">需保有相同 ID 與內容的本機素材。設定檔包含素材指紋。</p>
        <ul v-if="importPreview.document.input_assets.length">
          <li v-for="asset in importPreview.document.input_assets" :key="asset.role">
            {{ asset.role === 'mask' ? '遮罩' : '來源' }} · {{ asset.id }} · {{ asset.width }} ×
            {{ asset.height }} · {{ asset.sha256 }}
          </li>
        </ul>
        <p v-for="warning in importPreview.warnings" :key="warning" class="notice warning">{{
          warning
        }}</p>
        <details v-if="differences.length">
          <summary>查看 {{ differences.length }} 個不同欄位</summary>
          <dl>
            <template v-for="[key, value] in differences" :key="key">
              <dt>{{ key }}</dt
              ><dd>{{ JSON.stringify(value) }}</dd>
            </template>
          </dl>
        </details>
        <div class="actions">
          <button type="button" :disabled="!importPreview.loadable" @click="applyImport"
            >套用匯入設定</button
          >
          <button type="button" @click="importPreview = null">取消匯入</button>
        </div>
      </section>
    </fieldset>
    <fieldset :disabled="busy || disabled">
      <legend>專用比較方案</legend>
      <p v-if="experiment" class="notice">
        已連結 {{ experiment.plan_title }} · {{ experiment.selection.variant_id }}
        <button type="button" @click="emit('detach')">解除比較關聯</button>
      </p>
      <label :for="uid + '-axis'">比較參數</label>
      <select :id="uid + '-axis'" v-model="axis">
        <option v-for="[key, label] in axes" :key="key" :value="key">{{ label }}</option>
      </select>
      <label :for="uid + '-values'">比較值（2–4 個，以逗號分隔）</label>
      <input :id="uid + '-values'" v-model="values" maxlength="100" />
      <div class="actions"
        ><button type="button" @click="previewPlan">預覽專用比較方案</button></div
      >
      <label :for="uid + '-plan-import'">匯入專用比較方案 JSON</label>
      <input
        :id="uid + '-plan-import'"
        type="file"
        accept=".json,application/json"
        @change="importFile($event, true)"
      />
      <div v-if="preview" class="notice" aria-label="比較方案預覽">
        <p>{{ preview.title }} · {{ preview.axis }} · {{ preview.values.join('、') }}</p>
        <div class="actions">
          <button type="button" @click="savePlan">保存專用比較方案</button>
          <button
            type="button"
            @click="download(preview, 'model-atelier-specialized-comparison.json')"
            >匯出比較方案 JSON</button
          >
        </div>
      </div>
      <label :for="uid + '-plan'">已保存比較方案</label>
      <select :id="uid + '-plan'" v-model="planId">
        <option value="">選擇比較方案</option>
        <option v-for="row in plans" :key="row.id" :value="row.id"
          >{{ row.title }} · {{ row.axis }}{{ row.archived ? '（已封存）' : '' }}</option
        >
      </select>
      <button type="button" :disabled="!planId" @click="loadPlan">讀取專用比較方案</button>
      <section v-if="plan" :aria-label="plan.plan.title">
        <h4>{{ plan.plan.title }} · {{ plan.plan.axis }}</h4>
        <div class="actions">
          <a :href="'/api/specialized/comparisons/' + plan.id + '/document'">下載已保存方案</a>
          <button type="button" @click="archivePlan">{{
            plan.archived ? '還原方案' : '封存方案'
          }}</button>
          <button type="button" @click="run((signal) => readResults(signal))"
            >重讀已保存結果</button
          >
        </div>
        <ul>
          <li v-for="variant in plan.plan.variants" :key="variant.id">
            <button type="button" :disabled="plan.archived" @click="applyVariant(variant)"
              >載入比較組 {{ variant.value }}</button
            >
            <ul>
              <li
                v-for="job in results?.variants.find((row) => row.variant_id === variant.id)?.runs"
                :key="job.id"
              >
                <a :href="'/api/jobs/' + job.id" target="_blank" rel="noopener">原任務紀錄</a> ·
                {{ job.status }}
                <button
                  v-if="job.status === 'completed'"
                  type="button"
                  @click="emit('gallery', job.id)"
                  >前往作品庫</button
                >
                <div v-for="artwork in job.artworks" :key="artwork.id">
                  <a
                    v-if="artwork.image_available"
                    :href="'/api/artworks/' + artwork.id + '/image'"
                    target="_blank"
                    rel="noopener"
                    >{{ artwork.title }}</a
                  >
                  <span v-else>{{ artwork.title }}（原圖遺失）</span>
                </div>
              </li>
            </ul>
          </li>
        </ul>
      </section>
    </fieldset>
  </details>
</template>

<style scoped>
.specialized-settings {
  min-width: 0;
  overflow-wrap: anywhere;
}
fieldset {
  min-width: 0;
  margin-block: 12px;
}
label,
select,
input {
  display: block;
  max-width: 100%;
}
.actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-block: 8px;
}
summary {
  cursor: pointer;
}
</style>
