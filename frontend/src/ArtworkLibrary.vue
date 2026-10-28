<script setup lang="ts">
import UiIcon from './UiIcon.vue'
import { vMasonry } from './masonry'
const layout = ref('fixed')
const importOpen = ref(false)
const sort = ref('latest')
const pageSize = ref(12)
function clearFilters() {
  search.value = ''
  modelFilter.value = ''
  favoritesOnly.value = false
}
function ratingSummary(ratings: Ratings) {
  const values = Object.values(ratings || {}).filter(
    (value): value is number => typeof value === 'number' && Number.isFinite(value),
  )
  return values.length
    ? '平均 ' +
        (values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1) +
        ' / 5 · 已評 ' +
        values.length +
        ' / 4 項'
    : '尚未評分'
}
function artworkDate(item: Artwork) {
  const date = new Date(item.created_at || item.imported_at)
  return Number.isNaN(date.getTime()) ? '日期未知' : date.toLocaleDateString('zh-TW')
}
function selectCollection(value: 'active' | 'archived', favorites = false) {
  scope.value = value
  favoritesOnly.value = favorites
}
import { api, apiResponse, ApiError } from './apiClient'
import { createRequestScope } from './requestScope'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  architectureLabel,
  fileHash,
  fileSize,
  metadataTime,
  safeMetadataUrl,
} from './modelMetadata'
import type { ModelMetadataSnapshot, LoraMetadataSnapshot } from './modelMetadata'
import LoraSnapshot from './LoraSnapshot.vue'
import ComponentSnapshot from './ComponentSnapshot.vue'
import ControlSnapshot from './ControlSnapshot.vue'
import ControlEdgePreview from './ControlEdgePreview.vue'
import StructureOutput from './StructureOutput.vue'
import { controlEdgeWorkflowId, structureWorkflowId, isControlWorkflow } from './controlSettings'
import ReferenceSnapshot from './ReferenceSnapshot.vue'
import RuntimeSnapshot from './RuntimeSnapshot.vue'
import ExperimentSnapshot from './ExperimentSnapshot.vue'
import type { ExperimentContext } from './experimentSettings'
import JobMeasurements from './JobMeasurements.vue'
import type { JobMeasurements as Measurements } from './jobMeasurements'
import ArtworkComparison from './ArtworkComparison.vue'
import {
  emptyRatings,
  ratingLabels,
  type Ratings,
  type ComparisonArtwork,
} from './artworkComparison'
import type { RuntimeMetadata } from './runtimeMetadata'
import { isInpaintWorkflow } from './inpaintSettings'
import { referenceWorkflowId } from './adapterSettings'
import ReferenceComponentsSnapshot from './ReferenceComponentsSnapshot.vue'
import { imageWorkflowId, type ReferenceSnapshot as ReferenceMetadata } from './referenceSettings'
import { fluxWorkflowId, type ComponentSnapshot as ComponentMetadata } from './fluxSettings'
import { isFluxExtension } from './fluxExtensions'
const props = defineProps<{ jobId?: string; comparing?: boolean }>()
const emit = defineEmits<{
  studio: []
  restore: [artworkId: string, workflowId?: string | null]
  dirty: [value: boolean]
  compare: [show: boolean]
}>()
type Parameters = {
  prompt: string | null
  negative_prompt: string | null
  seed: string | null
  steps: number | null
  cfg: number | null
  sampler: string | null
  scheduler: string | null
  denoise: number | null
}
type Artwork = {
  notes_truncated?: boolean
  experiment_context?: ExperimentContext | null
  measurements?: Measurements | null
  ratings: Ratings
  runtime_metadata?: RuntimeMetadata | null
  id: string
  job_id: string
  title: string
  checkpoint: string
  model_version: string
  model_metadata?: ModelMetadataSnapshot | null
  lora_metadata?: LoraMetadataSnapshot[] | null
  workflow_id?: string | null
  component_metadata?: ComponentMetadata[] | null
  reference_metadata?: ReferenceMetadata[] | null
  engine_url: string
  parameters: Parameters
  width: number
  height: number
  size: number
  created_at: string
  imported_at: string
  image_available: boolean
  thumbnail_available: boolean
  sha256: string
  favorite: boolean
  notes: string
  archived: boolean
  revision: number
  organization_updated_at: string | null
}
type Job = { id: string; status: string; checkpoint: string; created_at: string }
type ImportResult = {
  imported: Artwork[]
  existing: Artwork[]
  errors: { source: { filename: string }; message: string }[]
}
const items = ref<Artwork[]>([]),
  jobs = ref<Job[]>([]),
  selectedJob = ref(props.jobId || '')
const importing = ref(false)
const busy = ref(false),
  error = ref(''),
  message = ref(''),
  failures = ref<ImportResult['errors']>([])
const search = ref(''),
  selected = ref<Artwork | null>(null),
  preview = ref<HTMLDialogElement | null>(null)
const scope = ref<'active' | 'archived' | 'all'>('active'),
  favoritesOnly = ref(false),
  modelFilter = ref('')
const hasFilters = computed(
  () => !!(search.value.trim() || modelFilter.value.trim() || favoritesOnly.value),
)
const saving = ref(false),
  notesDraft = ref(''),
  organizationError = ref(''),
  organizationMessage = ref('')
const notesDirty = computed(
  () => selected.value !== null && notesDraft.value !== selected.value.notes,
)
const ratingsDraft = ref<Ratings>(emptyRatings())
const ratingsDirty = computed(
  () =>
    selected.value !== null &&
    JSON.stringify(ratingsDraft.value) !== JSON.stringify(selected.value.ratings),
)
type PageResult<T> = {
  items: T[]
  total: number
  all_total: number
  offset: number
  next_cursor: string | null
  previous_cursor: string | null
  models: string[]
  missing_ids: string[]
}
const comparisonIds = ref<string[]>([]),
  comparisonRecords = ref(new Map<string, Artwork>())
const comparisonItems = computed(() =>
  comparisonIds.value.map((id) => comparisonRecords.value.get(id)).filter((v): v is Artwork => !!v),
)
const batchMode = ref<'archive' | 'download' | 'refresh' | null>(null)
const batchCancel = ref(false)
const batchFailures = ref<{ id: string; title: string; message: string }[]>([])
const selectionReady = computed(
  () =>
    comparisonIds.value.length > 0 && comparisonItems.value.length === comparisonIds.value.length,
)
const canCompare = computed(
  () => selectionReady.value && comparisonIds.value.length >= 2 && comparisonIds.value.length <= 4,
)
function clearComparison() {
  if (saving.value) return
  comparisonIds.value = []
  comparisonRecords.value.clear()
  batchFailures.value = []
}
async function toggleComparison(id: string) {
  if (saving.value) return
  if (comparisonIds.value.includes(id)) {
    comparisonIds.value = comparisonIds.value.filter((v) => v !== id)
    comparisonRecords.value.delete(id)
    return
  }
  if (comparisonIds.value.length >= 100) return
  comparisonIds.value.push(id)
  try {
    const item = await api<Artwork>('artworks/' + id)
    if (comparisonIds.value.includes(id)) comparisonRecords.value.set(id, item)
  } catch (e) {
    comparisonIds.value = comparisonIds.value.filter((v) => v !== id)
    error.value = e instanceof Error ? e.message : '比較資料讀取失敗'
  }
}
function showComparison() {
  if (canCompare.value && !saving.value) emit('compare', true)
}
watch(
  () => props.comparing,
  () => {
    preview.value?.close()
    selected.value = null
  },
)
let disposed = false
async function refreshSelection() {
  if (saving.value) return
  saving.value = true
  batchMode.value = 'refresh'
  batchFailures.value = []
  try {
    for (const id of comparisonIds.value) {
      if (disposed) break
      try {
        replaceItem(await api<Artwork>('artworks/' + id))
      } catch (e) {
        batchFailures.value.push({
          id,
          title: comparisonRecords.value.get(id)?.title || id,
          message: e instanceof Error ? e.message : '讀取失敗',
        })
      }
    }
    message.value = batchFailures.value.length
      ? '部分選取狀態無法更新，請查看逐項結果。'
      : '已重新讀取所選作品；請確認後再執行操作。'
  } finally {
    saving.value = false
    batchMode.value = null
  }
}
async function archiveSelection() {
  if (saving.value || busy.value || !selectionReady.value) return
  const archived = scope.value !== 'archived'
  const chosen = [...comparisonItems.value]
  saving.value = true
  batchMode.value = 'archive'
  batchCancel.value = false
  batchFailures.value = []
  error.value = ''
  let completed = 0
  try {
    for (const item of chosen) {
      if (disposed || batchCancel.value) break
      try {
        if (item.archived !== archived) {
          const updated = await api<Artwork>(`artworks/${item.id}/organization`, 'PATCH', {
            revision: item.revision,
            archived,
          })
          replaceItem(updated)
        }
        completed++
        comparisonIds.value = comparisonIds.value.filter((id) => id !== item.id)
        comparisonRecords.value.delete(item.id)
      } catch (e) {
        const uncertain = !(e instanceof ApiError) || !e.conclusive
        batchFailures.value.push({
          id: item.id,
          title: item.title,
          message:
            (e instanceof Error ? e.message : '保存失敗') +
            (uncertain ? ' 結果尚未確認，已停止後續操作；請重新讀取選取狀態。' : ''),
        })
        if (uncertain) break
      }
    }
    message.value =
      `已${archived ? '封存' : '還原'} ${completed} 件；保留 ${comparisonIds.value.length} 件選取。` +
      (batchCancel.value ? '已停止，已完成的項目會保留。' : '')
    if (!disposed) await read(null, false)
  } finally {
    saving.value = false
    batchMode.value = null
  }
}
async function downloadSelection() {
  if (saving.value || !selectionReady.value) return
  saving.value = true
  batchMode.value = 'download'
  error.value = ''
  try {
    const response = await apiResponse('artwork-downloads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artwork_ids: comparisonIds.value }),
    })
    const blob = await response.blob()
    if (disposed) return
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'model-atelier-artworks.zip'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 60000)
    message.value = `已交給瀏覽器下載 ${comparisonIds.value.length} 張原圖（ZIP），選取保持不變。`
  } catch (e) {
    error.value = e instanceof Error ? e.message : '下載失敗，選取保持不變。'
  } finally {
    saving.value = false
    batchMode.value = null
  }
}
function inspectComparison(item: ComparisonArtwork) {
  const value = comparisonRecords.value.get(item.id)
  if (value) void open(value)
}
const modelChoices = ref<string[]>([]),
  total = ref(0),
  allTotal = ref<number | null>(null),
  offset = ref(0)
const nextCursor = ref<string | null>(null),
  previousCursor = ref<string | null>(null),
  taskCursor = ref<string | null>(null)
const taskBusy = ref(false)
const completed = computed(() => jobs.value)
const visible = computed(() => items.value)
const reads = createRequestScope(),
  details = createRequestScope(),
  taskReads = createRequestScope()
async function read(cursor: string | null = null, loadTasks = true) {
  const request = reads.begin()
  busy.value = true
  const query = new URLSearchParams({
    limit: String(pageSize.value),
    scope: scope.value,
    q: search.value,
    favorites_only: String(favoritesOnly.value),
    model: modelFilter.value,
    sort: sort.value,
  })
  if (cursor) query.set('cursor', cursor)
  try {
    const [artworks, tasks] = await Promise.all([
      api<PageResult<Artwork>>('library/artworks?' + query, 'GET', undefined, request.signal),
      loadTasks
        ? api<PageResult<Job>>(
            'library/jobs?status=completed&limit=40',
            'GET',
            undefined,
            request.signal,
          )
        : Promise.resolve(null),
    ])
    if (!request.isCurrent()) return
    items.value = artworks.items
    total.value = artworks.total
    allTotal.value = Number.isSafeInteger(artworks.all_total) ? artworks.all_total : null
    offset.value = artworks.offset
    modelChoices.value = artworks.models
    nextCursor.value = artworks.next_cursor
    previousCursor.value = artworks.previous_cursor
    if (artworks.missing_ids.length) message.value = '部分項目已移除，請重新整理取得最新清單。'
    if (tasks) {
      taskReads.cancel()
      taskBusy.value = false
      jobs.value = tasks.items
      taskCursor.value = tasks.next_cursor
      if (selectedJob.value && !jobs.value.some((job) => job.id === selectedJob.value)) {
        const selected = await api<Job>(
          'jobs/' + selectedJob.value,
          'GET',
          undefined,
          request.signal,
        )
        if (!request.isCurrent()) return
        if (selected.status === 'completed') jobs.value.push(selected)
      }
      if (!completed.value.some((job) => job.id === selectedJob.value))
        selectedJob.value = completed.value[0]?.id || ''
    }
  } catch (e) {
    if (request.isCurrent()) error.value = e instanceof Error ? e.message : '讀取失敗'
  } finally {
    if (request.isCurrent()) busy.value = false
  }
}
async function olderTasks() {
  if (!taskCursor.value || taskBusy.value) return
  const request = taskReads.begin()
  taskBusy.value = true
  try {
    const result = await api<PageResult<Job>>(
      'library/jobs?' +
        new URLSearchParams({ limit: '40', status: 'completed', cursor: taskCursor.value }),
      'GET',
      undefined,
      request.signal,
    )
    if (!request.isCurrent()) return
    const ids = new Set(jobs.value.map((job) => job.id))
    jobs.value = [...jobs.value, ...result.items.filter((job) => !ids.has(job.id))]
    taskCursor.value = result.next_cursor
  } catch (e) {
    if (request.isCurrent()) error.value = e instanceof Error ? e.message : '讀取失敗'
  } finally {
    if (request.isCurrent()) taskBusy.value = false
  }
}
async function changePage(cursor: string | null) {
  error.value = ''
  await read(cursor, false)
}
let filterTimer: ReturnType<typeof setTimeout>
watch([search, scope, favoritesOnly, modelFilter, sort, pageSize], () => {
  clearTimeout(filterTimer)
  reads.cancel()
  busy.value = true
  filterTimer = setTimeout(() => {
    void changePage(null)
  }, 250)
})
async function refresh() {
  if (busy.value || saving.value) return
  busy.value = true
  error.value = ''
  try {
    await read()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '讀取失敗'
  } finally {
    busy.value = false
  }
}
async function importImages() {
  if (busy.value || saving.value || !selectedJob.value) return
  importing.value = true
  busy.value = true
  error.value = ''
  message.value = ''
  failures.value = []
  try {
    const result = await api<ImportResult>(`jobs/${selectedJob.value}/artworks`, 'POST')
    failures.value = result.errors
    message.value = `新增 ${result.imported.length} 張 · 已匯入 ${result.existing.length} 張 · 失敗 ${result.errors.length} 張。`
    if (result.errors.length) message.value += ' 已成功保存的作品會保留，可再次匯入補齊。'
    await read()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '匯入失敗'
  } finally {
    busy.value = false
    importing.value = false
  }
}
async function open(item: Artwork) {
  const request = details.begin()
  try {
    if (!Object.hasOwn(item, 'parameters'))
      item = await api<Artwork>('artworks/' + item.id, 'GET', undefined, request.signal)
    if (!request.isCurrent()) return
  } catch (e) {
    if (request.isCurrent()) error.value = e instanceof Error ? e.message : '作品詳情讀取失敗'
    return
  }
  selected.value = item
  notesDraft.value = item.notes
  ratingsDraft.value = { ...item.ratings }
  organizationError.value = ''
  organizationMessage.value = ''
  await nextTick()
  preview.value?.showModal()
}
function restore(item: Artwork) {
  if (!closePreview()) return
  emit('restore', item.id, item.workflow_id)
}
function closePreview() {
  if (saving.value) return false
  if (
    (notesDirty.value || ratingsDirty.value) &&
    !window.confirm('筆記或評分尚未保存，確定關閉並放棄變更？')
  )
    return false
  preview.value?.close()
  return true
}
function replaceItem(item: Artwork) {
  items.value = items.value.map((value) => (value.id === item.id ? item : value))
  if (comparisonRecords.value.has(item.id)) comparisonRecords.value.set(item.id, item)
  if (selected.value?.id === item.id) selected.value = item
}
async function organize(
  item: Artwork,
  changes: Partial<Pick<Artwork, 'favorite' | 'notes' | 'archived' | 'ratings'>>,
  feedback: string,
) {
  if (busy.value || saving.value) return
  saving.value = true
  error.value = ''
  organizationError.value = ''
  organizationMessage.value = ''
  try {
    const updated = await api<Artwork>(`artworks/${item.id}/organization`, 'PATCH', {
      revision: item.revision,
      ...changes,
    })
    replaceItem(updated)
    if (Object.hasOwn(changes, 'notes')) notesDraft.value = updated.notes
    if (Object.hasOwn(changes, 'ratings')) ratingsDraft.value = { ...updated.ratings }
    message.value = feedback
    organizationMessage.value = feedback
  } catch (e) {
    const text = e instanceof Error ? e.message : '保存失敗，筆記仍保留在表單。'
    if (selected.value?.id === item.id) organizationError.value = text
    else error.value = text
  } finally {
    saving.value = false
  }
}
function archive(item: Artwork) {
  if (selected.value?.id === item.id && (notesDirty.value || ratingsDirty.value)) {
    organizationError.value = '請先保存筆記及評分，再變更封存狀態。'
    return
  }
  void organize(
    item,
    { archived: !item.archived },
    item.archived ? '作品已還原到使用中的作品。' : '作品已封存，可在「已封存」篩選中還原。',
  )
}
async function reloadNotes() {
  const item = selected.value
  if (!item || saving.value) return
  if (
    (notesDirty.value || ratingsDirty.value) &&
    !window.confirm('重新讀取會放棄尚未保存的筆記與評分，確定繼續？')
  )
    return
  saving.value = true
  organizationError.value = ''
  organizationMessage.value = ''
  const request = details.begin()
  try {
    const updated = await api<Artwork>(`artworks/${item.id}`, 'GET', undefined, request.signal)
    if (!request.isCurrent() || selected.value?.id !== item.id) return
    replaceItem(updated)
    notesDraft.value = updated.notes
    ratingsDraft.value = { ...updated.ratings }
    organizationMessage.value = '已讀取最新筆記、評分與作品狀態。'
  } catch (e) {
    if (request.isCurrent()) organizationError.value = e instanceof Error ? e.message : '讀取失敗'
  } finally {
    saving.value = false
  }
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (notesDirty.value || ratingsDirty.value || saving.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
watch(
  [notesDirty, ratingsDirty, saving],
  ([notes, ratings, pending]) => emit('dirty', notes || ratings || pending),
  { flush: 'sync' },
)
const imageUrl = (item: Artwork, thumbnail = false) =>
  `/api/artworks/${item.id}/image${thumbnail ? '?thumbnail=true' : ''}`
onMounted(() => {
  window.addEventListener('beforeunload', beforeUnload)
  void refresh()
})
onBeforeUnmount(() => {
  disposed = true
  clearTimeout(filterTimer)
  reads.dispose()
  details.dispose()
  taskReads.dispose()
  window.removeEventListener('beforeunload', beforeUnload)
  emit('dirty', false)
})
</script>

<template>
  <div v-show="!comparing">
    <p v-if="busy" class="footnote" role="status">正在讀取或匯入作品，請稍候…</p>
    <div class="page-intro"
      ><p>瀏覽、收藏與重用設定，延續每一次創作。</p
      ><button class="primary" @click="importOpen = !importOpen">匯入任務結果</button></div
    ><div v-show="importOpen || !!jobId"
      ><article class="panel import-panel">
        <p>把已完成任務的圖片保存到作品庫。匯入後可離線瀏覽，並保留原圖與生成設定。</p>
        <div class="import-controls"
          ><label for="artwork-job"
            >已完成的任務<select
              id="artwork-job"
              v-model="selectedJob"
              :disabled="busy || !completed.length"
              ><option value="">{{ completed.length ? '選擇任務' : '尚無已完成任務' }}</option
              ><option v-for="job in completed" :key="job.id" :value="job.id"
                >{{ new Date(job.created_at).toLocaleString() }} · {{ job.checkpoint }} ·
                {{ job.id.slice(0, 8) }}</option
              ></select
            ></label
          ><button class="primary" :disabled="busy || !selectedJob" @click="importImages">{{
            busy ? '處理中…' : '匯入／補齊圖片'
          }}</button></div
        >
        <button v-if="taskCursor" class="secondary" :disabled="taskBusy || busy" @click="olderTasks"
          >載入較早已完成任務</button
        >
        <p class="footnote"
          >PNG、JPEG、WebP · 每張最多 32 MiB、3200 萬像素。匯入時需連接原 ComfyUI
          引擎；重複匯入會略過已保存的作品。</p
        >
        <p v-if="!completed.length" class="footnote"
          >先在創作工作台生成圖片並更新任務狀態，再回到這裡匯入。</p
        >
        <button class="secondary" @click="emit('studio')">前往創作工作台 →</button>
      </article></div
    >
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <p v-if="message" class="notice" role="status">{{ message }}</p>
    <ul v-if="failures.length" class="notice warning" role="alert"
      ><li v-for="(failure, index) in failures" :key="index"
        >{{ failure.source.filename }}：{{ failure.message }}</li
      ></ul
    >
    <div class="gallery-browser-tools">
      <label class="gallery-search" for="artwork-search"
        ><span class="sr-only">搜尋作品</span
        ><input
          id="artwork-search"
          v-model="search"
          :disabled="saving || importing"
          maxlength="200"
          type="search"
          placeholder="搜尋作品名稱"
      /></label>
      <div class="purpose-tabs" role="group" aria-label="作品狀態">
        <button
          :aria-pressed="scope === 'active' && !favoritesOnly"
          :disabled="saving || importing"
          @click="selectCollection('active')"
          >全部</button
        >
        <button
          :aria-pressed="favoritesOnly"
          :disabled="saving || importing"
          @click="selectCollection('active', true)"
          >已收藏</button
        >
        <button
          :aria-pressed="scope === 'archived'"
          :disabled="saving || importing"
          @click="selectCollection('archived')"
          >已封存</button
        >
      </div>
      <label class="gallery-model" for="artwork-model"
        ><span class="sr-only">模型篩選</span
        ><input
          id="artwork-model"
          v-model="modelFilter"
          :disabled="saving || importing"
          list="artwork-model-options"
          maxlength="2048"
          placeholder="全部模型" /><datalist id="artwork-model-options"
          ><option v-for="name in modelChoices" :key="name" :value="name" /></datalist
      ></label>
      <div class="view-switch" role="group" aria-label="作品排版"
        ><span>排版</span
        ><button class="secondary" :aria-pressed="layout === 'masonry'" @click="layout = 'masonry'"
          >瀑布流</button
        ><button class="secondary" :aria-pressed="layout === 'fixed'" @click="layout = 'fixed'"
          >固定</button
        ></div
      >
    </div>
    <div class="gallery-list-meta"
      ><span class="footnote" role="status"
        >{{ total }} 張符合／全部 {{ allTotal ?? '未知' }} 張（含封存） · 第
        {{ Math.floor(offset / pageSize) + 1 }} / {{ Math.max(1, Math.ceil(total / pageSize)) }} 頁
        · 本頁 {{ items.length }} 張</span
      ><label
        >排序<select v-model="sort" :disabled="saving || importing"
          ><option value="latest">最新</option
          ><option value="oldest">最早</option
          ><option value="rating">評分最高</option
          ><option value="model">模型</option></select
        ></label
      ></div
    >
    <article v-if="!visible.length" class="panel placeholder"
      ><h2>{{
        busy
          ? '讀取作品中…'
          : hasFilters
            ? '沒有符合的作品'
            : scope === 'archived'
              ? '尚無封存作品'
              : '作品庫還沒有作品'
      }}</h2
      ><p>{{
        hasFilters
          ? '調整搜尋、模型或收藏篩選；封存作品可在「已封存」中還原。'
          : scope === 'archived'
            ? '封存作品會出現在這裡，可隨時還原。'
            : '完成生成後，選擇上方任務匯入圖片。作品會保存在這台平台主機。'
      }}</p
      ><button v-if="hasFilters" class="secondary" :disabled="busy || saving" @click="clearFilters"
        >清除搜尋與篩選</button
      ><p v-if="hasFilters" class="footnote"
        >保留目前的{{
          scope === 'archived' ? '已封存' : scope === 'all' ? '全部作品' : '使用中'
        }}範圍。</p
      ><button v-else-if="!busy" class="primary" @click="emit('studio')"
        >前往創作工作台</button
      ></article
    >
    <div
      class="artwork-grid"
      v-masonry="layout === 'masonry'"
      :class="{ masonry: layout === 'masonry' }"
      ><article v-for="item in visible" :key="item.id" class="panel artwork-card">
        <button class="artwork-cover" :aria-label="'查看作品 ' + item.title" @click="open(item)"
          ><img
            v-if="item.thumbnail_available"
            :src="imageUrl(item, true)"
            :alt="item.title"
            loading="lazy"
            @error="item.thumbnail_available = false"
          /><span v-else>縮圖無法讀取 · 點此查看資料</span></button
        ><button
          class="gallery-overlay favorite"
          :aria-label="(item.favorite ? '取消收藏：' : '收藏作品：') + item.title"
          :aria-pressed="!!item.favorite"
          :disabled="busy || saving"
          @click="
            organize(
              item,
              { favorite: !item.favorite },
              item.favorite ? '已取消收藏。' : '已加入收藏。',
            )
          "
          ><span aria-hidden="true">★</span></button
        ><button
          class="gallery-overlay select"
          :aria-pressed="comparisonIds.includes(item.id)"
          :aria-label="'選取作品：' + item.title"
          :disabled="saving || (!comparisonIds.includes(item.id) && comparisonIds.length >= 100)"
          @click="toggleComparison(item.id)"
          ><UiIcon name="check" :size="20" /></button
        ><div class="gallery-card-meta"
          ><div class="card-title"
            ><h2>{{ item.title }}</h2
            ><span v-if="item.archived" class="archive-badge">已封存</span
            ><span v-if="item.favorite" class="favorite-badge">★ 收藏</span></div
          ><p>{{ item.checkpoint }} · {{ item.width }}×{{ item.height }}</p
          ><p class="gallery-rating" title="只計入已評項目；未評項目不當作零分">{{
            ratingSummary(item.ratings)
          }}</p
          ><p class="gallery-date">{{ artworkDate(item) }}</p
          ><details
            ><summary>資訊與操作</summary
            ><p
              >{{ item.width }} × {{ item.height }} ·
              {{ (item.size / 1024 / 1024).toFixed(2) }} MiB</p
            >
            <p>{{ item.checkpoint }} · 版本 {{ item.model_version }}</p>
            <p v-if="item.notes" class="note-excerpt"
              >{{ item.notes.slice(0, 160)
              }}{{ item.notes_truncated || item.notes.length > 160 ? '…' : '' }}</p
            >
            <p v-if="isControlWorkflow(item.workflow_id)">Canny 結構參考 · 輪廓條件</p>
            <p v-if="item.workflow_id === referenceWorkflowId">畫風／角色外觀參考 · 非身份鎖定</p>
            <p v-if="isInpaintWorkflow(item.workflow_id)">局部編輯 · 原圖與遮罩</p>
            <p v-if="item.workflow_id === imageWorkflowId"
              >圖生圖 · 參考素材 {{ item.reference_metadata?.length ?? 0 }} 張</p
            >
            <p v-for="(lora, index) in item.lora_metadata ?? []" :key="index"
              >LoRA {{ lora.name }} · 版本 {{ lora.version?.trim() || '未知' }}</p
            >
            <p v-if="!item.image_available" class="missing"
              >原圖已遺失，請從備份還原；生成參數仍保留。</p
            >
            <div class="organization-actions"
              ><button
                class="secondary"
                :aria-label="(item.archived ? '還原作品：' : '封存作品：') + item.title"
                :disabled="busy || saving"
                @click="archive(item)"
                >{{ item.archived ? '還原作品' : '封存作品' }}</button
              ></div
            >
            <div class="artwork-actions"
              ><button
                class="secondary"
                :aria-label="'預覽與參數：' + item.title"
                @click="open(item)"
                >預覽與參數</button
              ><button
                class="secondary"
                :aria-label="'載入創作設定：' + item.title"
                @click="restore(item)"
                >載入創作設定 →</button
              ><a v-if="item.image_available" :href="imageUrl(item) + '?download=true'"
                >下載原圖 ↓</a
              ></div
            ></details
          ></div
        ></article
      ></div
    >
    <div class="library-footer"
      ><label class="page-size-control"
        >每頁<select
          v-model.number="pageSize"
          :disabled="busy || saving || importing"
          aria-label="每頁作品筆數"
          ><option v-for="size in [4, 12, 24]" :key="size" :value="size">{{ size }}</option></select
        >張</label
      >
      <div v-if="previousCursor || nextCursor" role="group" aria-label="作品分頁"
        ><button
          class="secondary"
          :disabled="busy || saving || !previousCursor"
          @click="changePage(previousCursor)"
          >上一頁</button
        ><button
          class="secondary"
          :disabled="busy || saving || !nextCursor"
          @click="changePage(nextCursor)"
          >下一頁</button
        ></div
      >
      <button class="secondary" :disabled="busy || saving" @click="refresh">重新整理</button>
      <details
        ><summary>清單與篩選說明</summary
        ><p class="footnote"
          >本次清單成員固定；重新整理或變更篩選可取得新增項目。比較選擇跨頁保留。</p
        ><label
          >作品狀態<select id="artwork-scope" v-model="scope" :disabled="saving || importing"
            ><option value="active">使用中</option
            ><option value="archived">已封存</option
            ><option value="all">全部作品</option></select
          ></label
        ></details
      >
    </div>
    <section v-if="comparisonIds.length" class="gallery-selectionbar" aria-label="已選作品">
      <span role="status">已選 {{ comparisonIds.length }} 件</span>
      <button class="primary" :disabled="!canCompare || saving" @click="showComparison"
        >並排比較（2–4 張）</button
      >
      <button
        class="secondary"
        :disabled="!selectionReady || busy || saving"
        @click="archiveSelection"
        >{{ scope === 'archived' ? '批次還原' : '批次封存' }}</button
      >
      <button class="secondary" :disabled="!selectionReady || saving" @click="downloadSelection"
        >批次下載原圖（{{ comparisonIds.length }} 張）</button
      >
      <button class="secondary" :disabled="saving" @click="clearComparison">清除選取</button>
      <span v-if="!selectionReady" class="footnote">正在讀取選取資料…</span>
      <span v-else-if="comparisonIds.length > 4" class="footnote"
        >比較最多選 4 張；批次管理最多選 100 件。</span
      >
      <template v-if="batchMode"
        ><span role="status">{{
          batchMode === 'archive'
            ? '正在逐項保存…'
            : batchMode === 'download'
              ? '正在準備 ZIP…'
              : '正在讀取選取狀態…'
        }}</span>
        <button
          v-if="batchMode === 'archive'"
          class="secondary"
          :disabled="batchCancel"
          @click="batchCancel = true"
          >停止後續操作</button
        >
      </template>
    </section>
    <div v-if="batchFailures.length" class="notice warning" role="alert">
      <ul
        ><li v-for="failure in batchFailures" :key="failure.id"
          >{{ failure.title }}：{{ failure.message }}</li
        ></ul
      >
      <button class="secondary" :disabled="saving" @click="refreshSelection"
        >重新讀取選取狀態</button
      >
    </div>
  </div>
  <div v-if="comparing" class="gallery-comparison-page">
    <div class="page-intro"
      ><p>原圖並排查看，保留生成參數與人工評分。</p
      ><button class="secondary" @click="emit('compare', false)">返回作品庫</button></div
    >
    <ArtworkComparison
      v-if="comparisonItems.length <= 4"
      :items="comparisonItems"
      @remove="toggleComparison"
      @clear="clearComparison"
      @inspect="inspectComparison"
    />
    <p v-if="comparisonItems.length > 4" class="notice" role="status"
      >比較最多選 4 張，請返回作品庫調整選取。</p
    >
    <p v-if="!comparisonItems.length" class="notice" role="status"
      >尚未選取作品。請返回作品庫選取 2–4 張，再按「並排比較」。</p
    >
  </div>
  <dialog
    ref="preview"
    class="artwork-dialog"
    aria-labelledby="artwork-preview-title"
    @cancel.prevent="closePreview"
    @close="selected = null"
  >
    <template v-if="selected">
      <div class="preview-grid"
        ><div class="preview-image"
          ><img
            v-if="selected.image_available"
            :src="imageUrl(selected)"
            :alt="selected.title"
            @error="selected.image_available = false"
          /><p v-else class="notice warning">原圖無法讀取，請重新整理作品庫或從備份還原。</p></div
        >
        <div class="artwork-info"
          ><div class="preview-heading"
            ><h2 id="artwork-preview-title"
              >{{ selected.title }}<small v-if="selected.archived"> · 已封存</small></h2
            ><div class="preview-top-actions"
              ><button
                class="secondary"
                :disabled="busy || saving || notesDirty || ratingsDirty"
                @click="archive(selected)"
                >{{ selected.archived ? '還原作品' : '封存作品' }}</button
              ><button class="secondary" :disabled="saving" autofocus @click="closePreview"
                >關閉</button
              ></div
            ></div
          ><dl class="artwork-facts"
            ><div
              ><dt>模型</dt><dd>{{ selected.checkpoint }}</dd></div
            ><div
              ><dt>尺寸</dt><dd>{{ selected.width }} × {{ selected.height }}</dd></div
            ><div
              ><dt>像素量</dt
              ><dd>{{ ((selected.width * selected.height) / 1e6).toFixed(2) }} MP</dd></div
            ><div
              ><dt>狀態</dt
              ><dd>{{
                selected.archived ? '已封存' : selected.favorite ? '已收藏' : '一般'
              }}</dd></div
            ></dl
          ><section class="organization-panel" aria-label="作品管理"
            ><h3>作品管理</h3
            ><p v-if="busy" class="footnote" role="status">作品清單讀取中，完成後即可保存。</p
            ><div class="organization-actions"
              ><button
                class="secondary"
                :aria-pressed="!!selected.favorite"
                :disabled="busy || saving"
                @click="
                  organize(
                    selected,
                    { favorite: !selected.favorite },
                    selected.favorite ? '已取消收藏。' : '已加入收藏。',
                  )
                "
                >{{ selected.favorite ? '★ 已收藏' : '☆ 收藏' }}</button
              ></div
            ><form @submit.prevent="organize(selected, { notes: notesDraft }, '筆記已保存。')"
              ><label for="artwork-notes">作品筆記</label
              ><textarea
                id="artwork-notes"
                v-model="notesDraft"
                rows="5"
                maxlength="10000"
                :disabled="saving"
                aria-describedby="artwork-notes-help"
                placeholder="記下這次實驗的觀察、用途或下次想調整的參數。"
              ></textarea
              ><p id="artwork-notes-help" class="footnote"
                >最多 10,000 字 ·
                {{
                  notesDirty ? '有尚未保存的變更' : '筆記已同步'
                }}。封存後仍可預覽、下載與還原。</p
              ><div class="organization-actions"
                ><button class="primary" :disabled="busy || saving || !notesDirty">{{
                  saving ? '保存中…' : '保存筆記'
                }}</button
                ><button type="button" class="secondary" :disabled="saving" @click="reloadNotes"
                  >重新讀取筆記</button
                ></div
              ></form
            ><p class="footnote"
              >修訂 {{ selected.revision }} ·
              {{
                selected.organization_updated_at
                  ? new Date(selected.organization_updated_at).toLocaleString()
                  : '尚未整理'
              }}</p
            ><p v-if="organizationError" class="notice warning" role="alert">{{
              organizationError
            }}</p
            ><p v-if="organizationMessage" class="notice" role="status">{{
              organizationMessage
            }}</p></section
          ><div class="artwork-actions"
            ><button class="primary" @click="restore(selected)">載入創作設定 →</button
            ><a v-if="selected.image_available" :href="imageUrl(selected) + '?download=true'"
              >下載原圖 ↓</a
            ><a :href="`/api/artworks/${selected.id}/workflow`">下載完整工作流程</a
            ><a :href="`/api/jobs/${selected.job_id}`" target="_blank" rel="noopener"
              >原始任務 JSON ↗</a
            ></div
          ><p class="footnote">載入設定只填入創作台，不會自動生成。封存後可隨時還原。</p
          ><details class="artwork-extra"
            ><summary>生成設定、人工評分與完整來源</summary
            ><section class="organization-panel" aria-label="人工評分"
              ><h3>人工評分</h3
              ><p class="footnote"
                >1 最低、5 最高；未觀察／不適用請留空。這是個人觀察，不代表模型自動驗證。</p
              ><form @submit.prevent="organize(selected, { ratings: ratingsDraft }, '評分已保存。')"
                ><label v-for="(label, key) in ratingLabels" :key="key" :for="'rating-' + key"
                  >{{ label
                  }}<select
                    :id="'rating-' + key"
                    :aria-label="label"
                    v-model="ratingsDraft[key]"
                    :disabled="saving"
                    ><option :value="null">未評分／不適用</option
                    ><option v-for="score in 5" :key="score" :value="score"
                      >{{ score }} / 5</option
                    ></select
                  ></label
                ><p v-if="ratingsDirty" class="footnote">評分有尚未保存變更。</p
                ><button class="primary" :disabled="busy || saving || !ratingsDirty"
                  >保存評分</button
                ></form
              ></section
            >
            <h3>生成設定</h3>
            <dl
              ><dt>Checkpoint</dt><dd>{{ selected.checkpoint }}</dd
              ><dt>模型版本（提交時登記）</dt><dd>{{ selected.model_version }}</dd
              ><dt>圖片尺寸</dt><dd>{{ selected.width }} × {{ selected.height }}</dd
              ><dt>Seed</dt><dd>{{ selected.parameters.seed ?? '未知' }}</dd
              ><dt>Steps / CFG</dt
              ><dd
                >{{ selected.parameters.steps ?? '未知' }} /
                {{ selected.parameters.cfg ?? '未知' }}</dd
              ><dt>Sampler / Scheduler</dt
              ><dd
                >{{ selected.parameters.sampler ?? '未知' }} /
                {{ selected.parameters.scheduler ?? '未知' }}</dd
              ><dt>Denoise</dt><dd>{{ selected.parameters.denoise ?? '未知' }}</dd></dl
            >
            <h3>畫面描述</h3>
            <p class="prompt">{{
              selected.parameters.prompt ?? '無法從此工作流程解析，請查看完整 JSON。'
            }}</p>
            <h3>負面提示詞</h3>
            <p class="prompt">{{ selected.parameters.negative_prompt || '未設定或無法解析' }}</p>
            <details class="model-snapshot"
              ><summary>提交時模型資料</summary>
              <template v-if="selected.model_metadata"
                ><p class="footnote"
                  >保留任務提交時的使用者登記，不隨模型庫後續編輯改動；不代表平台已驗證檔案、授權或相容性。</p
                ><dl>
                  <dt>模型檔名</dt><dd>{{ selected.model_metadata.name || '未知' }}</dd>
                  <dt>登記版本</dt><dd>{{ selected.model_metadata.version?.trim() || '未知' }}</dd>
                  <dt>登記架構</dt
                  ><dd>{{ architectureLabel(selected.model_metadata.architecture) }}</dd>
                  <dt>模型檔案大小</dt><dd>{{ fileSize(selected.model_metadata.size_bytes) }}</dd>
                  <dt>模型檔案 SHA-256</dt
                  ><dd class="file-hash">{{ fileHash(selected.model_metadata.sha256) }}</dd>
                  <dt>模型來源</dt
                  ><dd
                    ><a
                      v-if="safeMetadataUrl(selected.model_metadata.source_url)"
                      :href="safeMetadataUrl(selected.model_metadata.source_url)"
                      target="_blank"
                      rel="noopener noreferrer"
                      >查看當時登記來源 ↗</a
                    ><span v-else>未知</span></dd
                  >
                  <dt>授權名稱／標記</dt
                  ><dd>{{ selected.model_metadata.license_name?.trim() || '未知' }}</dd>
                  <dt>授權條款網址</dt
                  ><dd
                    ><a
                      v-if="safeMetadataUrl(selected.model_metadata.license_url)"
                      :href="safeMetadataUrl(selected.model_metadata.license_url)"
                      target="_blank"
                      rel="noopener noreferrer"
                      >查看當時登記條款 ↗</a
                    ><span v-else>未知</span></dd
                  >
                  <dt>登記資料更新</dt
                  ><dd>{{ metadataTime(selected.model_metadata.metadata_updated_at) }}</dd>
                  <dt>快照保存</dt><dd>{{ metadataTime(selected.model_metadata.captured_at) }}</dd>
                </dl></template
              >
              <p v-else class="footnote"
                >此作品尚無提交時的模型資料快照，當時架構、檔案識別及授權資訊未知。</p
              >
            </details>
            <LoraSnapshot
              v-if="
                !selected.workflow_id ||
                isFluxExtension(selected.workflow_id) ||
                selected.workflow_id === imageWorkflowId ||
                isInpaintWorkflow(selected.workflow_id) ||
                isControlWorkflow(selected.workflow_id)
              "
              :items="selected.lora_metadata"
            />
            <a
              v-if="
                !selected.workflow_id ||
                ['checkpoint-text2image-v1', imageWorkflowId, fluxWorkflowId].includes(
                  selected.workflow_id,
                )
              "
              :href="`/api/artworks/${selected.id}/settings-export`"
              >匯出創作設定（含來源快照）</a
            >
            <ControlSnapshot
              v-if="isControlWorkflow(selected.workflow_id)"
              :items="selected.component_metadata"
            />
            <ReferenceComponentsSnapshot
              v-else-if="selected.workflow_id === referenceWorkflowId"
              :items="selected.component_metadata"
            />
            <ComponentSnapshot v-else :items="selected.component_metadata" />
            <ExperimentSnapshot :item="selected.experiment_context" />
            <RuntimeSnapshot :item="selected.runtime_metadata" />
            <JobMeasurements :item="selected.measurements" />
            <StructureOutput
              v-if="selected.workflow_id === structureWorkflowId"
              :job-id="selected.job_id"
            />
            <ControlEdgePreview
              v-if="selected.workflow_id === controlEdgeWorkflowId"
              :key="selected.id"
              :job-id="selected.job_id"
              :artwork-id="selected.id"
            />
            <p
              v-else-if="
                selected.workflow_id !== structureWorkflowId &&
                isControlWorkflow(selected.workflow_id)
              "
              class="footnote"
              >舊版 v1 沒有保存同次邊緣輸出，不會重新計算歷史圖。</p
            >
            <ReferenceSnapshot
              :items="selected.reference_metadata"
              :job-id="selected.job_id"
              :processed-ready="true"
            />
            <details
              ><summary>作品來源紀錄</summary><p>原引擎：{{ selected.engine_url }}</p
              ><p>任務：{{ selected.job_id }}</p
              ><p>提交：{{ new Date(selected.created_at).toLocaleString() }}</p
              ><p>匯入：{{ new Date(selected.imported_at).toLocaleString() }}</p
              ><p class="file-hash">作品原圖 SHA-256：{{ selected.sha256 }}</p></details
            ></details
          ></div
        ></div
      ></template
    >
  </dialog>
</template>

<style scoped>
.gallery-selectionbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 16px;
  margin: 20px 0 0;
  position: sticky;
  bottom: 10px;
  z-index: 3;
  justify-content: center;
  border: 1px solid var(--border-control);
  border-radius: 12px;
  background: #202d25;
}
.gallery-selectionbar > span:first-child {
  white-space: nowrap;
}
.gallery-selectionbar button {
  white-space: nowrap;
}
.gallery-comparison-page {
  min-width: 0;
}
.import-panel {
  background: linear-gradient(120deg, #253b2d, #191d20);
}
.import-controls,
.artwork-toolbar,
.artwork-actions {
  display: flex;
  align-items: end;
  gap: 12px;
  flex-wrap: wrap;
}
.import-controls label,
.artwork-toolbar label {
  display: grid;
  gap: 9px;
  font-size: 12px;
  flex: 1;
  min-width: 0;
}
.import-controls select {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border-control);
  border-radius: 7px;
  background: var(--surface-input);
  color: var(--text-primary);
  font: inherit;
}
.artwork-toolbar {
  margin: 24px 0;
}
.artwork-toolbar .muted {
  align-self: center;
  font-size: 12px;
}
.artwork-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}
.artwork-card {
  min-width: 0;
  margin-bottom: 0;
}
.artwork-cover {
  display: grid;
  place-items: center;
  width: 100%;
  height: 230px;
  padding: 0;
  background: #101617;
  color: #9fb1a5;
  border-radius: 8px;
  overflow: hidden;
}
.artwork-cover img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.artwork-card h2 {
  font-size: 14px;
  overflow-wrap: anywhere;
  margin-top: 18px;
}
.artwork-card p {
  font-size: 11px;
  overflow-wrap: anywhere;
}
.artwork-actions {
  align-items: center;
  margin-top: 18px;
  font-size: 12px;
}
.artwork-actions a {
  color: #c5dfba;
}
.missing {
  color: #ebc4a1;
}
.artwork-dialog {
  background: #191f20;
  color: var(--text-primary);
  border: 1px solid var(--border-control);
  border-radius: 14px;
  padding: 24px;
  width: min(1160px, 94vw);
  max-height: 90vh;
}
.artwork-dialog::backdrop {
  background: #000b;
}
.preview-heading {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}
.preview-heading h2 {
  font-size: 18px;
  overflow-wrap: anywhere;
}
.preview-heading button {
  flex-shrink: 0;
}
.preview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 24px;
}
.preview-image {
  background: #101617;
  display: grid;
  place-items: center;
  align-self: start;
  min-height: 200px;
}
.preview-image img {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
}
.artwork-info {
  font-size: 12px;
  min-width: 0;
  overflow-wrap: anywhere;
}
.artwork-info h3 {
  font-size: 13px;
  margin-top: 20px;
}
.artwork-info dl {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 10px;
}
.artwork-info dt {
  color: #9fb1a5;
}
.artwork-info dd {
  margin: 0;
}
.prompt {
  white-space: pre-wrap;
  max-height: 220px;
  overflow: auto;
}
.artwork-info details {
  margin-top: 24px;
}
.artwork-info summary {
  cursor: pointer;
}
@media (max-width: 1100px) {
  .artwork-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 700px) {
  .artwork-grid,
  .preview-grid {
    grid-template-columns: 1fr;
  }
  .import-controls label,
  .artwork-toolbar label {
    flex-basis: 100%;
  }
  .artwork-dialog {
    padding: 16px;
  }
  .preview-heading h2 {
    font-size: 14px;
  }
}
.model-snapshot a {
  color: #c5dfba;
}
.file-hash {
  font-family: monospace;
  line-height: 1.7;
}
.artwork-toolbar .favorite-filter {
  white-space: nowrap;
  min-width: 90px;
}
.favorite-filter input {
  width: auto;
  flex-shrink: 0;
}
.organization-panel select {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 10px;
  font: inherit;
}
.artwork-toolbar select {
  width: 100%;
  min-width: 0;
  padding: 11px;
  font-size: 12px;
}
.artwork-toolbar .favorite-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 18px;
}
.card-title h2 {
  margin: 0;
}
.archive-badge,
.favorite-badge {
  font-size: 10px;
  border: 1px solid var(--border-control);
  border-radius: 20px;
  padding: 4px 8px;
  color: #c8dfbd;
}
.note-excerpt {
  white-space: pre-wrap;
  color: #cbd7cf;
  max-height: 100px;
  overflow: hidden;
}
.organization-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.organization-panel {
  border: 1px solid var(--border-control);
  background: #1c2824;
  border-radius: 10px;
  padding: 16px;
}
.organization-panel h3 {
  margin-top: 0;
}
.organization-panel label {
  display: block;
  margin: 18px 0 10px;
}
.organization-panel textarea {
  display: block;
  box-sizing: border-box;
  width: 100%;
  padding: 12px;
  resize: vertical;
  line-height: 1.6;
}
.organization-panel .notice {
  padding: 12px;
  margin-bottom: 0;
}
.preview-heading small {
  font-size: 12px;
  font-weight: normal;
  color: var(--text-muted);
}
</style>
