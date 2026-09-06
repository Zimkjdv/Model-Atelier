<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
const props = defineProps<{ jobId?: string }>()
const emit = defineEmits<{ studio: [] }>()
type Parameters = { prompt: string | null; negative_prompt: string | null; seed: string | null; steps: number | null; cfg: number | null; sampler: string | null; scheduler: string | null; denoise: number | null }
type Artwork = { id: string; job_id: string; title: string; checkpoint: string; model_version: string; engine_url: string; parameters: Parameters; width: number; height: number; size: number; created_at: string; imported_at: string; image_available: boolean; thumbnail_available: boolean; sha256: string }
type Job = { id: string; status: string; checkpoint: string; created_at: string }
type ImportResult = { imported: Artwork[]; existing: Artwork[]; errors: { source: { filename: string }; message: string }[] }
const items = ref<Artwork[]>([]), jobs = ref<Job[]>([]), selectedJob = ref(props.jobId || '')
const busy = ref(false), error = ref(''), message = ref(''), failures = ref<ImportResult['errors']>([])
const search = ref(''), selected = ref<Artwork | null>(null), preview = ref<HTMLDialogElement | null>(null)
const completed = computed(() => jobs.value.filter(job => job.status === 'completed'))
const visible = computed(() => items.value.filter(item => [item.title, item.checkpoint, item.parameters.prompt || ''].join(' ').toLowerCase().includes(search.value.toLowerCase())))
async function api<T>(path: string, method = 'GET'): Promise<T> {
  const response = await fetch('/api/' + path, { method })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : '無法讀取作品資料，請稍後再試。')
  }
  return response.json()
}
async function read() {
  const [artworks, tasks] = await Promise.all([api<Artwork[]>('artworks'), api<Job[]>('jobs')])
  items.value = artworks; jobs.value = tasks
  if (!completed.value.some(job => job.id === selectedJob.value)) selectedJob.value = completed.value[0]?.id || ''
}
async function refresh() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await read() }
  catch (e) { error.value = e instanceof Error ? e.message : '讀取失敗' }
  finally { busy.value = false }
}
async function importImages() {
  if (busy.value || !selectedJob.value) return
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
  await nextTick()
  preview.value?.showModal()
}
const imageUrl = (item: Artwork, thumbnail = false) => `/api/artworks/${item.id}/image${thumbnail ? '?thumbnail=true' : ''}`
const importedCount = (job: Job) => items.value.filter(item => item.job_id === job.id).length
onMounted(refresh)
</script>

<template>
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
  <div class="artwork-toolbar"><label for="artwork-search">搜尋作品<input id="artwork-search" v-model="search" type="search" placeholder="檔名、模型或畫面描述"></label><button class="secondary" :disabled="busy" @click="refresh">重新整理</button><span class="muted">{{ visible.length }} 張作品</span></div>
  <article v-if="!visible.length" class="panel placeholder"><h2>{{ busy ? '讀取作品中…' : items.length ? '沒有符合的作品' : '第一張作品，從一次生成開始' }}</h2><p>{{ items.length ? '試試其他搜尋文字。' : '完成生成後，選擇上方任務匯入圖片。作品會保存在這台平台主機。' }}</p></article>
  <div class="artwork-grid"><article v-for="item in visible" :key="item.id" class="panel artwork-card">
    <button class="artwork-cover" :aria-label="'查看作品 ' + item.title" @click="open(item)"><img v-if="item.thumbnail_available" :src="imageUrl(item, true)" :alt="item.title" loading="lazy" @error="item.thumbnail_available = false"><span v-else>縮圖無法讀取 · 點此查看資料</span></button>
    <h2>{{ item.title }}</h2><p>{{ item.width }} × {{ item.height }} · {{ (item.size / 1024 / 1024).toFixed(2) }} MiB</p><p>{{ item.checkpoint }} · 版本 {{ item.model_version }}</p>
    <p v-if="!item.image_available" class="missing">原圖已遺失，請從備份還原；生成參數仍保留。</p>
    <div class="artwork-actions"><button class="secondary" @click="open(item)">預覽與參數</button><a v-if="item.image_available" :href="imageUrl(item) + '?download=true'">下載原圖 ↓</a></div>
  </article></div>
  <dialog ref="preview" class="artwork-dialog" aria-labelledby="artwork-preview-title" @close="selected = null">
    <template v-if="selected"><div class="preview-heading"><h2 id="artwork-preview-title">{{ selected.title }}</h2><button class="secondary" autofocus @click="preview?.close()">關閉 ×</button></div>
      <div class="preview-grid"><div class="preview-image"><img v-if="selected.image_available" :src="imageUrl(selected)" :alt="selected.title" @error="selected.image_available = false"><p v-else class="notice warning">原圖無法讀取，請重新整理作品庫或從備份還原。</p></div>
        <div class="artwork-info"><h3>生成設定</h3><dl><dt>Checkpoint</dt><dd>{{ selected.checkpoint }}</dd><dt>模型版本（提交時登記）</dt><dd>{{ selected.model_version }}</dd><dt>圖片尺寸</dt><dd>{{ selected.width }} × {{ selected.height }}</dd><dt>Seed</dt><dd>{{ selected.parameters.seed ?? '未知' }}</dd><dt>Steps / CFG</dt><dd>{{ selected.parameters.steps ?? '未知' }} / {{ selected.parameters.cfg ?? '未知' }}</dd><dt>Sampler / Scheduler</dt><dd>{{ selected.parameters.sampler ?? '未知' }} / {{ selected.parameters.scheduler ?? '未知' }}</dd><dt>Denoise</dt><dd>{{ selected.parameters.denoise ?? '未知' }}</dd></dl>
        <h3>畫面描述</h3><p class="prompt">{{ selected.parameters.prompt ?? '無法從此工作流程解析，請查看完整 JSON。' }}</p><h3>負面提示詞</h3><p class="prompt">{{ selected.parameters.negative_prompt || '未設定或無法解析' }}</p>
        <details><summary>來源紀錄</summary><p>原引擎：{{ selected.engine_url }}</p><p>任務：{{ selected.job_id }}</p><p>提交：{{ new Date(selected.created_at).toLocaleString() }}</p><p>匯入：{{ new Date(selected.imported_at).toLocaleString() }}</p><p>原圖 SHA-256：{{ selected.sha256 }}</p></details>
        <div class="artwork-actions"><a v-if="selected.image_available" :href="imageUrl(selected) + '?download=true'">下載原圖 ↓</a><a :href="`/api/artworks/${selected.id}/workflow`">下載完整工作流程</a><a :href="`/api/jobs/${selected.job_id}`" target="_blank" rel="noopener">原始任務 JSON ↗</a></div>
        </div></div></template>
  </dialog>
</template>

<style scoped>
.import-panel{background:linear-gradient(120deg,#253b2d,#191d20)}.import-controls,.artwork-toolbar,.artwork-actions{display:flex;align-items:end;gap:12px;flex-wrap:wrap}.import-controls label,.artwork-toolbar label{display:grid;gap:9px;font-size:12px;flex:1;min-width:0}.import-controls select{width:100%;padding:12px;border:1px solid #4c5855;border-radius:7px;background:#101517;color:#e5ebe7;font:inherit}.artwork-toolbar{margin:24px 0}.artwork-toolbar .muted{align-self:center;font-size:12px}.artwork-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.artwork-card{min-width:0;margin-bottom:0}.artwork-cover{display:grid;place-items:center;width:100%;height:230px;padding:0;background:#101617;color:#9fb1a5;border-radius:8px;overflow:hidden}.artwork-cover img{width:100%;height:100%;object-fit:contain}.artwork-card h2{font-size:14px;overflow-wrap:anywhere;margin-top:18px}.artwork-card p{font-size:11px;overflow-wrap:anywhere}.artwork-actions{align-items:center;margin-top:18px;font-size:12px}.artwork-actions a{color:#c5dfba}.missing{color:#ebc4a1}.artwork-dialog{background:#191f20;color:#e5ebe7;border:1px solid #4c5855;border-radius:14px;padding:24px;width:min(1160px,94vw);max-height:90vh}.artwork-dialog::backdrop{background:#000b}.preview-heading{display:flex;align-items:start;justify-content:space-between;gap:20px;margin-bottom:20px}.preview-heading h2{font-size:18px;overflow-wrap:anywhere}.preview-heading button{flex-shrink:0}.preview-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:24px}.preview-image{background:#101617;display:grid;place-items:center;align-self:start;min-height:200px}.preview-image img{max-width:100%;max-height:70vh;object-fit:contain}.artwork-info{font-size:12px;min-width:0;overflow-wrap:anywhere}.artwork-info h3{font-size:13px;margin-top:20px}.artwork-info dl{display:grid;grid-template-columns:1fr 1.2fr;gap:10px}.artwork-info dt{color:#9fb1a5}.artwork-info dd{margin:0}.prompt{white-space:pre-wrap;max-height:220px;overflow:auto}.artwork-info details{margin-top:24px}.artwork-info summary{cursor:pointer}@media(max-width:1100px){.artwork-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.artwork-grid,.preview-grid{grid-template-columns:1fr}.import-controls label,.artwork-toolbar label{flex-basis:100%}.artwork-dialog{padding:16px}.preview-heading h2{font-size:14px}}
</style>
