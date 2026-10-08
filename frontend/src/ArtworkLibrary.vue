<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { architectureLabel, fileHash, fileSize, metadataTime, safeMetadataUrl } from './modelMetadata'
import type { ModelMetadataSnapshot, LoraMetadataSnapshot } from './modelMetadata'
import LoraSnapshot from './LoraSnapshot.vue'
import ComponentSnapshot from './ComponentSnapshot.vue'
import ReferenceSnapshot from './ReferenceSnapshot.vue'
import RuntimeSnapshot from './RuntimeSnapshot.vue'
import JobMeasurements from './JobMeasurements.vue'
import type { JobMeasurements as Measurements } from './jobMeasurements'
import ArtworkComparison from './ArtworkComparison.vue'
import { emptyRatings, ratingLabels, type Ratings, type ComparisonArtwork } from './artworkComparison'
import type { RuntimeMetadata } from './runtimeMetadata'
import { imageWorkflowId, type ReferenceSnapshot as ReferenceMetadata } from './referenceSettings'
import type { ComponentSnapshot as ComponentMetadata } from './fluxSettings'
const props = defineProps<{ jobId?: string }>()
const emit = defineEmits<{ studio: []; restore: [artworkId: string, workflowId?: string | null]; dirty: [value: boolean] }>()
type Parameters = { prompt: string | null; negative_prompt: string | null; seed: string | null; steps: number | null; cfg: number | null; sampler: string | null; scheduler: string | null; denoise: number | null }
type Artwork = { measurements?: Measurements | null; ratings: Ratings; runtime_metadata?: RuntimeMetadata | null; id: string; job_id: string; title: string; checkpoint: string; model_version: string; model_metadata?: ModelMetadataSnapshot | null; lora_metadata?: LoraMetadataSnapshot[] | null; workflow_id?: string | null; component_metadata?: ComponentMetadata[] | null; reference_metadata?: ReferenceMetadata[] | null; engine_url: string; parameters: Parameters; width: number; height: number; size: number; created_at: string; imported_at: string; image_available: boolean; thumbnail_available: boolean; sha256: string; favorite: boolean; notes: string; archived: boolean; revision: number; organization_updated_at: string | null }
type Job = { id: string; status: string; checkpoint: string; created_at: string }
type ImportResult = { imported: Artwork[]; existing: Artwork[]; errors: { source: { filename: string }; message: string }[] }
const items = ref<Artwork[]>([]), jobs = ref<Job[]>([]), selectedJob = ref(props.jobId || '')
const busy = ref(false), error = ref(''), message = ref(''), failures = ref<ImportResult['errors']>([])
const search = ref(''), selected = ref<Artwork | null>(null), preview = ref<HTMLDialogElement | null>(null)
const scope = ref<'active' | 'archived' | 'all'>('active'), favoritesOnly = ref(false), modelFilter = ref('')
const saving = ref(false), notesDraft = ref(''), organizationError = ref(''), organizationMessage = ref('')
const notesDirty = computed(() => selected.value !== null && notesDraft.value !== selected.value.notes)
const ratingsDraft = ref<Ratings>(emptyRatings())
const ratingsDirty = computed(() => selected.value !== null && JSON.stringify(ratingsDraft.value) !== JSON.stringify(selected.value.ratings))
const comparisonIds = ref<string[]>([])
const comparisonItems = computed(() => comparisonIds.value.map(id => items.value.find(item => item.id === id)).filter((v): v is Artwork => !!v))
function toggleComparison(id: string) {
  if (comparisonIds.value.includes(id)) comparisonIds.value = comparisonIds.value.filter(v => v !== id)
  else if (comparisonIds.value.length < 4) comparisonIds.value.push(id)
}
function inspectComparison(item: ComparisonArtwork) { const value = items.value.find(v => v.id === item.id); if (value) void open(value) }
const modelChoices = computed(() => [...new Set(items.value.map(item => item.checkpoint))].sort())
const archiveCount = computed(() => items.value.filter(item => item.archived).length)
const completed = computed(() => jobs.value.filter(job => job.status === 'completed'))
const visible = computed(() => items.value.filter(item => (scope.value === 'all' || item.archived === (scope.value === 'archived')) &&
  (!favoritesOnly.value || item.favorite) && (!modelFilter.value || item.checkpoint === modelFilter.value) &&
  [item.title, item.checkpoint, item.model_version, item.notes, item.parameters.prompt || '', ...(item.lora_metadata ?? []).map(lora => lora.name + ' ' + lora.version)].join(' ').toLowerCase().includes(search.value.trim().toLowerCase())))
async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api/' + path, { method, ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : '無法讀取作品資料，請稍後再試。')
  }
  return response.json()
}
async function read() {
  const [artworks, tasks] = await Promise.all([api<Artwork[]>('artworks?scope=all'), api<Job[]>('jobs')])
  items.value = artworks; jobs.value = tasks
  if (!completed.value.some(job => job.id === selectedJob.value)) selectedJob.value = completed.value[0]?.id || ''
}
async function refresh() {
  if (busy.value || saving.value) return
  busy.value = true; error.value = ''
  try { await read() }
  catch (e) { error.value = e instanceof Error ? e.message : '讀取失敗' }
  finally { busy.value = false }
}
async function importImages() {
  if (busy.value || saving.value || !selectedJob.value) return
  busy.value = true; error.value = ''; message.value = ''; failures.value = []
  try {
    const result = await api<ImportResult>(`jobs/${selectedJob.value}/artworks`, 'POST')
    failures.value = result.errors
    message.value = `新增 ${result.imported.length} 張 · 已匯入 ${result.existing.length} 張 · 失敗 ${result.errors.length} 張。`
    if (result.errors.length) message.value += ' 已成功保存的作品會保留，可再次匯入補齊。'
    await read()
  } catch (e) { error.value = e instanceof Error ? e.message : '匯入失敗' }
  finally { busy.value = false }
}
async function open(item: Artwork) {
  selected.value = item
  notesDraft.value = item.notes; ratingsDraft.value = { ...item.ratings }; organizationError.value = ''; organizationMessage.value = ''
  await nextTick()
  preview.value?.showModal()
}
function restore(item: Artwork) {
  if (!closePreview()) return
  emit('restore', item.id, item.workflow_id)
}
function closePreview() {
  if (saving.value) return false
  if ((notesDirty.value || ratingsDirty.value) && !window.confirm('筆記或評分尚未保存，確定關閉並放棄變更？')) return false
  preview.value?.close()
  return true
}
function replaceItem(item: Artwork) {
  items.value = items.value.map(value => value.id === item.id ? item : value)
  if (selected.value?.id === item.id) selected.value = item
}
async function organize(item: Artwork, changes: Partial<Pick<Artwork, 'favorite' | 'notes' | 'archived' | 'ratings'>>, feedback: string) {
  if (busy.value || saving.value) return
  saving.value = true; error.value = ''; organizationError.value = ''; organizationMessage.value = ''
  try {
    const updated = await api<Artwork>(`artworks/${item.id}/organization`, 'PATCH', { revision: item.revision, ...changes })
    replaceItem(updated)
    if (Object.hasOwn(changes, 'notes')) notesDraft.value = updated.notes
    if (Object.hasOwn(changes, 'ratings')) ratingsDraft.value = { ...updated.ratings }
    message.value = feedback; organizationMessage.value = feedback
  } catch (e) {
    const text = e instanceof Error ? e.message : '保存失敗，筆記仍保留在表單。'
    if (selected.value?.id === item.id) organizationError.value = text
    else error.value = text
  } finally { saving.value = false }
}
function archive(item: Artwork) {
  if (selected.value?.id === item.id && (notesDirty.value || ratingsDirty.value)) {
    organizationError.value = '請先保存筆記及評分，再變更封存狀態。'
    return
  }
  void organize(item, { archived: !item.archived }, item.archived ? '作品已還原到使用中的作品。' : '作品已封存，可在「已封存」篩選中還原。')
}
async function reloadNotes() {
  const item = selected.value
  if (!item || saving.value) return
  if ((notesDirty.value || ratingsDirty.value) && !window.confirm('重新讀取會放棄尚未保存的筆記與評分，確定繼續？')) return
  saving.value = true; organizationError.value = ''; organizationMessage.value = ''
  try {
    const updated = await api<Artwork>(`artworks/${item.id}`)
    replaceItem(updated); notesDraft.value = updated.notes; ratingsDraft.value = { ...updated.ratings }; organizationMessage.value = '已讀取最新筆記、評分與作品狀態。'
  } catch (e) { organizationError.value = e instanceof Error ? e.message : '讀取失敗' }
  finally { saving.value = false }
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (notesDirty.value || ratingsDirty.value || saving.value) { event.preventDefault(); event.returnValue = '' }
}
watch([notesDirty, ratingsDirty, saving], ([notes, ratings, pending]) => emit('dirty', notes || ratings || pending), { flush: 'sync' })
const imageUrl = (item: Artwork, thumbnail = false) => `/api/artworks/${item.id}/image${thumbnail ? '?thumbnail=true' : ''}`
const importedCount = (job: Job) => items.value.filter(item => item.job_id === job.id).length
onMounted(() => { window.addEventListener('beforeunload', beforeUnload); void refresh() })
onBeforeUnmount(() => { window.removeEventListener('beforeunload', beforeUnload); emit('dirty', false) })
</script>

<template>
  <p v-if="busy" class="footnote" role="status">正在讀取或匯入作品，請稍候…</p>
  <article class="panel import-panel">
    <span class="chip">YOUR COLLECTION</span><h2>留下每一次創作</h2>
    <p>把已完成任務的圖片保存到作品庫。匯入後可離線瀏覽，並保留原圖與生成設定。</p>
    <div class="import-controls"><label for="artwork-job">已完成的任務<select id="artwork-job" v-model="selectedJob" :disabled="busy || !completed.length"><option value="">{{ completed.length ? '選擇任務' : '尚無已完成任務' }}</option><option v-for="job in completed" :key="job.id" :value="job.id">{{ new Date(job.created_at).toLocaleString() }} · {{ job.checkpoint }} · 已匯入 {{ importedCount(job) }} 張 · {{ job.id.slice(0, 8) }}</option></select></label><button class="primary" :disabled="busy || !selectedJob" @click="importImages">{{ busy ? '處理中…' : '匯入／補齊圖片' }}</button></div>
    <p class="footnote">PNG、JPEG、WebP · 每張最多 32 MiB、3200 萬像素。匯入時需連接原 ComfyUI 引擎；重複匯入會略過已保存的作品。</p>
    <p v-if="!completed.length" class="footnote">先在創作工作台生成圖片並更新任務狀態，再回到這裡匯入。</p>
    <button class="secondary" @click="emit('studio')">前往創作工作台 →</button>
  </article>
  <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
  <p v-if="message" class="notice" role="status">{{ message }}</p>
  <ul v-if="failures.length" class="notice warning" role="alert"><li v-for="(failure, index) in failures" :key="index">{{ failure.source.filename }}：{{ failure.message }}</li></ul>
  <div class="artwork-toolbar"><label for="artwork-search">搜尋作品<input id="artwork-search" v-model="search" type="search" placeholder="檔名、模型、筆記或畫面描述"></label><label for="artwork-scope">作品狀態<select id="artwork-scope" v-model="scope"><option value="active">使用中</option><option value="archived">已封存</option><option value="all">全部作品</option></select></label><label for="artwork-model">模型篩選<select id="artwork-model" v-model="modelFilter"><option value="">所有模型</option><option v-for="name in modelChoices" :key="name" :value="name">{{ name }}</option></select></label><label class="favorite-filter"><input v-model="favoritesOnly" type="checkbox">只看收藏</label><button class="secondary" :disabled="busy || saving" @click="refresh">重新整理</button><span class="muted" role="status">{{ visible.length }} / {{ items.length }} 張作品 · 已封存 {{ archiveCount }} 張</span></div>
  <article v-if="!visible.length" class="panel placeholder"><h2>{{ busy ? '讀取作品中…' : items.length ? '沒有符合的作品' : '第一張作品，從一次生成開始' }}</h2><p>{{ items.length ? '調整搜尋、模型或收藏篩選；封存作品可在「已封存」中還原。' : '完成生成後，選擇上方任務匯入圖片。作品會保存在這台平台主機。' }}</p></article>
  <ArtworkComparison :items="comparisonItems" @remove="toggleComparison" @clear="comparisonIds = []" @inspect="inspectComparison" />
  <div class="artwork-grid"><article v-for="item in visible" :key="item.id" class="panel artwork-card">
    <button class="artwork-cover" :aria-label="'查看作品 ' + item.title" @click="open(item)"><img v-if="item.thumbnail_available" :src="imageUrl(item, true)" :alt="item.title" loading="lazy" @error="item.thumbnail_available = false"><span v-else>縮圖無法讀取 · 點此查看資料</span></button>
    <div class="card-title"><h2>{{ item.title }}</h2><span v-if="item.archived" class="archive-badge">已封存</span><span v-if="item.favorite" class="favorite-badge">★ 收藏</span></div><p>{{ item.width }} × {{ item.height }} · {{ (item.size / 1024 / 1024).toFixed(2) }} MiB</p><p>{{ item.checkpoint }} · 版本 {{ item.model_version }}</p>
    <p v-if="item.notes" class="note-excerpt">{{ item.notes.slice(0, 160) }}{{ item.notes.length > 160 ? '…' : '' }}</p>
    <p v-if="item.workflow_id === imageWorkflowId">圖生圖 · 參考素材 {{ item.reference_metadata?.length ?? 0 }} 張</p>
    <p v-for="(lora, index) in item.lora_metadata ?? []" :key="index">LoRA {{ lora.name }} · 版本 {{ lora.version?.trim() || '未知' }}</p>
    <p v-if="!item.image_available" class="missing">原圖已遺失，請從備份還原；生成參數仍保留。</p>
    <div class="organization-actions"><button class="secondary" :aria-label="(item.favorite ? '取消收藏：' : '收藏作品：') + item.title" :aria-pressed="item.favorite" :disabled="busy || saving" @click="organize(item, { favorite: !item.favorite }, item.favorite ? '已取消收藏。' : '已加入收藏。')">{{ item.favorite ? '★ 已收藏' : '☆ 收藏' }}</button><button class="secondary" :aria-label="(item.archived ? '還原作品：' : '封存作品：') + item.title" :disabled="busy || saving" @click="archive(item)">{{ item.archived ? '還原作品' : '封存作品' }}</button></div>
    <button class="secondary" :aria-pressed="comparisonIds.includes(item.id)" :aria-label="'比較作品：' + item.title" :disabled="!comparisonIds.includes(item.id) && comparisonIds.length >= 4" @click="toggleComparison(item.id)">{{ comparisonIds.includes(item.id) ? '已加入比較' : '加入比較' }}</button>
    <div class="artwork-actions"><button class="secondary" :aria-label="'預覽與參數：' + item.title" @click="open(item)">預覽與參數</button><button class="secondary" :aria-label="'載入創作設定：' + item.title" @click="restore(item)">載入創作設定 →</button><a v-if="item.image_available" :href="imageUrl(item) + '?download=true'">下載原圖 ↓</a></div>
  </article></div>
  <dialog ref="preview" class="artwork-dialog" aria-labelledby="artwork-preview-title" @cancel.prevent="closePreview" @close="selected = null">
    <template v-if="selected"><div class="preview-heading"><h2 id="artwork-preview-title">{{ selected.title }}<small v-if="selected.archived"> · 已封存</small></h2><button class="secondary" :disabled="saving" autofocus @click="closePreview">關閉 ×</button></div>
      <div class="preview-grid"><div class="preview-image"><img v-if="selected.image_available" :src="imageUrl(selected)" :alt="selected.title" @error="selected.image_available = false"><p v-else class="notice warning">原圖無法讀取，請重新整理作品庫或從備份還原。</p></div>
        <div class="artwork-info"><section class="organization-panel" aria-label="作品管理"><h3>作品管理</h3><div class="organization-actions"><button class="secondary" :aria-pressed="selected.favorite" :disabled="saving" @click="organize(selected, { favorite: !selected.favorite }, selected.favorite ? '已取消收藏。' : '已加入收藏。')">{{ selected.favorite ? '★ 已收藏' : '☆ 收藏' }}</button><button class="secondary" :disabled="saving || notesDirty || ratingsDirty" @click="archive(selected)">{{ selected.archived ? '還原作品' : '封存作品' }}</button></div><form @submit.prevent="organize(selected, { notes: notesDraft }, '筆記已保存。')"><label for="artwork-notes">作品筆記</label><textarea id="artwork-notes" v-model="notesDraft" rows="5" maxlength="10000" :disabled="saving" aria-describedby="artwork-notes-help" placeholder="記下這次實驗的觀察、用途或下次想調整的參數。"></textarea><p id="artwork-notes-help" class="footnote">最多 10,000 字 · {{ notesDirty ? '有尚未保存的變更' : '筆記已同步' }}。封存後仍可預覽、下載與還原。</p><div class="organization-actions"><button class="primary" :disabled="saving || !notesDirty">{{ saving ? '保存中…' : '保存筆記' }}</button><button type="button" class="secondary" :disabled="saving" @click="reloadNotes">重新讀取筆記</button></div></form><p class="footnote">修訂 {{ selected.revision }} · {{ selected.organization_updated_at ? new Date(selected.organization_updated_at).toLocaleString() : '尚未整理' }}</p><p v-if="organizationError" class="notice warning" role="alert">{{ organizationError }}</p><p v-if="organizationMessage" class="notice" role="status">{{ organizationMessage }}</p></section><section class="organization-panel" aria-label="人工評分"><h3>人工評分</h3><p class="footnote">1 最低、5 最高；未觀察／不適用請留空。這是個人觀察，不代表模型自動驗證。</p><form @submit.prevent="organize(selected, { ratings: ratingsDraft }, '評分已保存。')"><label v-for="(label,key) in ratingLabels" :key="key" :for="'rating-' + key">{{ label }}<select :id="'rating-' + key" :aria-label="label" v-model="ratingsDraft[key]" :disabled="saving"><option :value="null">未評分／不適用</option><option v-for="score in 5" :key="score" :value="score">{{ score }} / 5</option></select></label><p v-if="ratingsDirty" class="footnote">評分有尚未保存變更。</p><button class="primary" :disabled="saving || !ratingsDirty">保存評分</button></form></section><h3>生成設定</h3><dl><dt>Checkpoint</dt><dd>{{ selected.checkpoint }}</dd><dt>模型版本（提交時登記）</dt><dd>{{ selected.model_version }}</dd><dt>圖片尺寸</dt><dd>{{ selected.width }} × {{ selected.height }}</dd><dt>Seed</dt><dd>{{ selected.parameters.seed ?? '未知' }}</dd><dt>Steps / CFG</dt><dd>{{ selected.parameters.steps ?? '未知' }} / {{ selected.parameters.cfg ?? '未知' }}</dd><dt>Sampler / Scheduler</dt><dd>{{ selected.parameters.sampler ?? '未知' }} / {{ selected.parameters.scheduler ?? '未知' }}</dd><dt>Denoise</dt><dd>{{ selected.parameters.denoise ?? '未知' }}</dd></dl>
        <h3>畫面描述</h3><p class="prompt">{{ selected.parameters.prompt ?? '無法從此工作流程解析，請查看完整 JSON。' }}</p><h3>負面提示詞</h3><p class="prompt">{{ selected.parameters.negative_prompt || '未設定或無法解析' }}</p>
        <details class="model-snapshot"><summary>提交時模型資料</summary>
          <template v-if="selected.model_metadata"><p class="footnote">保留任務提交時的使用者登記，不隨模型庫後續編輯改動；不代表平台已驗證檔案、授權或相容性。</p><dl>
            <dt>模型檔名</dt><dd>{{ selected.model_metadata.name || '未知' }}</dd>
            <dt>登記版本</dt><dd>{{ selected.model_metadata.version?.trim() || '未知' }}</dd>
            <dt>登記架構</dt><dd>{{ architectureLabel(selected.model_metadata.architecture) }}</dd>
            <dt>模型檔案大小</dt><dd>{{ fileSize(selected.model_metadata.size_bytes) }}</dd>
            <dt>模型檔案 SHA-256</dt><dd class="file-hash">{{ fileHash(selected.model_metadata.sha256) }}</dd>
            <dt>模型來源</dt><dd><a v-if="safeMetadataUrl(selected.model_metadata.source_url)" :href="safeMetadataUrl(selected.model_metadata.source_url)" target="_blank" rel="noopener noreferrer">查看當時登記來源 ↗</a><span v-else>未知</span></dd>
            <dt>授權名稱／標記</dt><dd>{{ selected.model_metadata.license_name?.trim() || '未知' }}</dd>
            <dt>授權條款網址</dt><dd><a v-if="safeMetadataUrl(selected.model_metadata.license_url)" :href="safeMetadataUrl(selected.model_metadata.license_url)" target="_blank" rel="noopener noreferrer">查看當時登記條款 ↗</a><span v-else>未知</span></dd>
            <dt>登記資料更新</dt><dd>{{ metadataTime(selected.model_metadata.metadata_updated_at) }}</dd>
            <dt>快照保存</dt><dd>{{ metadataTime(selected.model_metadata.captured_at) }}</dd>
          </dl></template>
          <p v-else class="footnote">此作品尚無提交時的模型資料快照，當時架構、檔案識別及授權資訊未知。</p>
        </details>
        <LoraSnapshot v-if="!selected.workflow_id || selected.workflow_id === imageWorkflowId" :items="selected.lora_metadata" />
        <a :href="`/api/artworks/${selected.id}/settings-export`">匯出創作設定（含來源快照）</a>
        <ComponentSnapshot :items="selected.component_metadata" />
        <RuntimeSnapshot :item="selected.runtime_metadata" /><JobMeasurements :item="selected.measurements" />
        <ReferenceSnapshot :items="selected.reference_metadata" :job-id="selected.job_id" :processed-ready="true" />
        <details><summary>作品來源紀錄</summary><p>原引擎：{{ selected.engine_url }}</p><p>任務：{{ selected.job_id }}</p><p>提交：{{ new Date(selected.created_at).toLocaleString() }}</p><p>匯入：{{ new Date(selected.imported_at).toLocaleString() }}</p><p class="file-hash">作品原圖 SHA-256：{{ selected.sha256 }}</p></details>
        <div class="artwork-actions"><button class="primary" @click="restore(selected)">載入創作設定 →</button><a v-if="selected.image_available" :href="imageUrl(selected) + '?download=true'">下載原圖 ↓</a><a :href="`/api/artworks/${selected.id}/workflow`">下載完整工作流程</a><a :href="`/api/jobs/${selected.job_id}`" target="_blank" rel="noopener">原始任務 JSON ↗</a></div>
        </div></div></template>
  </dialog>
</template>

<style scoped>
.import-panel{background:linear-gradient(120deg,#253b2d,#191d20)}.import-controls,.artwork-toolbar,.artwork-actions{display:flex;align-items:end;gap:12px;flex-wrap:wrap}.import-controls label,.artwork-toolbar label{display:grid;gap:9px;font-size:12px;flex:1;min-width:0}.import-controls select{width:100%;padding:12px;border:1px solid var(--border-control);border-radius:7px;background:var(--surface-input);color:var(--text-primary);font:inherit}.artwork-toolbar{margin:24px 0}.artwork-toolbar .muted{align-self:center;font-size:12px}.artwork-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.artwork-card{min-width:0;margin-bottom:0}.artwork-cover{display:grid;place-items:center;width:100%;height:230px;padding:0;background:#101617;color:#9fb1a5;border-radius:8px;overflow:hidden}.artwork-cover img{width:100%;height:100%;object-fit:contain}.artwork-card h2{font-size:14px;overflow-wrap:anywhere;margin-top:18px}.artwork-card p{font-size:11px;overflow-wrap:anywhere}.artwork-actions{align-items:center;margin-top:18px;font-size:12px}.artwork-actions a{color:#c5dfba}.missing{color:#ebc4a1}.artwork-dialog{background:#191f20;color:var(--text-primary);border:1px solid var(--border-control);border-radius:14px;padding:24px;width:min(1160px,94vw);max-height:90vh}.artwork-dialog::backdrop{background:#000b}.preview-heading{display:flex;align-items:start;justify-content:space-between;gap:20px;margin-bottom:20px}.preview-heading h2{font-size:18px;overflow-wrap:anywhere}.preview-heading button{flex-shrink:0}.preview-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:24px}.preview-image{background:#101617;display:grid;place-items:center;align-self:start;min-height:200px}.preview-image img{max-width:100%;max-height:70vh;object-fit:contain}.artwork-info{font-size:12px;min-width:0;overflow-wrap:anywhere}.artwork-info h3{font-size:13px;margin-top:20px}.artwork-info dl{display:grid;grid-template-columns:1fr 1.2fr;gap:10px}.artwork-info dt{color:#9fb1a5}.artwork-info dd{margin:0}.prompt{white-space:pre-wrap;max-height:220px;overflow:auto}.artwork-info details{margin-top:24px}.artwork-info summary{cursor:pointer}@media(max-width:1100px){.artwork-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.artwork-grid,.preview-grid{grid-template-columns:1fr}.import-controls label,.artwork-toolbar label{flex-basis:100%}.artwork-dialog{padding:16px}.preview-heading h2{font-size:14px}}
.model-snapshot a{color:#c5dfba}.file-hash{font-family:monospace;line-height:1.7}
.artwork-toolbar .favorite-filter{white-space:nowrap;min-width:90px}.favorite-filter input{width:auto;flex-shrink:0}.organization-panel select{display:block;width:100%;margin-top:8px;padding:10px;font:inherit}
.artwork-toolbar select{width:100%;min-width:0;padding:11px;font-size:12px}.artwork-toolbar .favorite-filter{display:flex;align-items:center;gap:8px;flex:0 0 auto}.card-title{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:18px}.card-title h2{margin:0}.archive-badge,.favorite-badge{font-size:10px;border:1px solid var(--border-control);border-radius:20px;padding:4px 8px;color:#c8dfbd}.note-excerpt{white-space:pre-wrap;color:#cbd7cf;max-height:100px;overflow:hidden}.organization-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:12px}.organization-panel{border:1px solid var(--border-control);background:#1c2824;border-radius:10px;padding:16px}.organization-panel h3{margin-top:0}.organization-panel label{display:block;margin:18px 0 10px}.organization-panel textarea{display:block;box-sizing:border-box;width:100%;padding:12px;resize:vertical;line-height:1.6}.organization-panel .notice{padding:12px;margin-bottom:0}.preview-heading small{font-size:12px;font-weight:normal;color:var(--text-muted)}
</style>
