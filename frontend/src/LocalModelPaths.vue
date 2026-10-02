<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

const props = defineProps<{ selectedEngineUrl?: string }>()
type Directory = {
  path: string
  status: 'existing' | 'missing' | 'unreadable'
  disk: { total: number | null; used: number | null; free: number | null } | null
  error: string | null
}
type Paths = {
  scope: 'managed_local_comfyui'
  managed_engine_url: string
  selected_engine_url: string
  revision: number
  updated_at: string | null
  paths: string[]
  default_directory: Directory
  directories: Directory[]
  application_status: 'unverified'
  restart_required: boolean
  warnings: string[]
}
class PathRequestError extends Error {
  constructor(message: string, readonly conflict = false) { super(message) }
}
const data = ref<Paths | null>(null), text = ref(''), saved = ref('')
const busy = ref(false), error = ref(''), feedback = ref(''), reloadChoice = ref(false), conflict = ref(false)
const dirty = computed(() => text.value !== saved.value)
const selectedEngine = computed(() => props.selectedEngineUrl || data.value?.selected_engine_url || '')
const scopeDiffers = computed(() => selectedEngine.value && data.value && selectedEngine.value !== data.value.managed_engine_url)
const pathCount = computed(() => text.value.split(/\r?\n/).filter(line => line.trim()).length)
const updatedAt = computed(() => {
  if (!data.value?.updated_at) return '尚無保存紀錄'
  const date = new Date(data.value.updated_at)
  return Number.isNaN(date.getTime()) ? '更新時間未知' : date.toLocaleString()
})
const directoryStatus = (value: Directory['status']) => ({ existing: '可讀取', missing: '目錄不存在', unreadable: '無法讀取' }[value] || '未知')
const diskSize = (value: number | null | undefined) => typeof value === 'number' && Number.isFinite(value) && value >= 0
  ? `${(value / 1024 ** 3).toFixed(2)} GiB` : '未知'
async function api(method = 'GET', body?: unknown): Promise<Paths> {
  const response = await fetch('/api/local-model-paths', { method,
    ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) })
  const value = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = value?.detail
    throw new PathRequestError(typeof detail === 'string' ? detail : typeof detail?.message === 'string'
      ? detail.message : method === 'GET' ? '無法讀取本機模型目錄設定，已保留目前輸入。' : '無法保存目錄設定，請確認每個目錄為可讀取的本機絕對路徑。',
      response.status === 409 && detail?.code === 'revision_conflict')
  }
  if (!value || value.scope !== 'managed_local_comfyui' || !Number.isSafeInteger(value.revision) || value.revision < 0 || !Array.isArray(value.paths))
    throw new PathRequestError('目錄設定回覆格式不正確，已保留目前輸入。')
  return value as Paths
}
function accept(value: Paths) {
  data.value = value; text.value = value.paths.join('\n'); saved.value = text.value
  conflict.value = false; reloadChoice.value = false
}
async function load() {
  if (busy.value) return
  busy.value = true; error.value = ''; feedback.value = ''
  try { accept(await api()) }
  catch (e) { error.value = e instanceof Error ? e.message : '無法讀取本機模型目錄；原有輸入已保留。' }
  finally { busy.value = false }
}
function requestReload() {
  if (dirty.value) reloadChoice.value = true
  else void load()
}
function parsePaths() {
  const lines = text.value.split(/\r?\n/)
  if (lines.some(line => /[\p{Cc}\p{Cf}]/u.test(line))) throw new Error('目錄文字含不可見控制字元，請重新輸入；每行只填一個本機絕對路徑。')
  const paths = lines.map(line => line.trim()).filter(Boolean)
  if (paths.length > 8) throw new Error('額外目錄最多 8 個；請刪除多餘的行再保存。')
  return paths
}
async function save() {
  if (busy.value || !data.value || conflict.value) return
  busy.value = true; error.value = ''; feedback.value = ''; reloadChoice.value = false
  try {
    const value = await api('PUT', { revision: data.value.revision, paths: parsePaths() })
    accept(value)
    feedback.value = '目錄設定已保存。請手動停止並重新啟動本機 ComfyUI，再到模型庫同步清單。'
  } catch (e) {
    conflict.value = e instanceof PathRequestError && e.conflict
    error.value = e instanceof Error ? e.message : '保存失敗，原有輸入已保留。'
  } finally { busy.value = false }
}
onMounted(() => { void load() })
</script>

<template>
  <article class="panel local-model-paths">
    <div class="paths-heading"><div><span class="chip">LOCAL CHECKPOINT DIRECTORIES</span><h2>本機模型目錄</h2></div><button type="button" class="secondary" :disabled="busy" @click="requestReload">重新讀取已保存設定</button></div>
    <p>將已存在的 checkpoint 目錄加入本機 ComfyUI 的搜尋範圍。支援其他本機磁碟，模型檔案保留原位置。</p>
    <p class="scope-note">適用本專案受管理的 ComfyUI：<code>{{ data?.managed_engine_url || 'http://127.0.0.1:8188' }}</code>（使用 start-comfyui.ps1 啟動）。</p>
    <p v-if="scopeDiffers" class="notice">目前連線設定為 {{ selectedEngine }}。下方路徑僅影響本機受管理的 ComfyUI，不會套用到其他或遠端引擎。</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }}<span v-if="conflict"> 你的輸入已保留，請先決定是否重新讀取已保存設定。</span></p>
    <p v-if="feedback" class="notice success" role="status">{{ feedback }}</p>
    <div v-if="reloadChoice" class="notice warning" role="alert"><p>重新讀取會取代目前未保存的目錄文字。</p><div class="paths-actions"><button type="button" class="secondary" :disabled="busy" @click="reloadChoice = false">保留目前輸入</button><button type="button" class="secondary" :disabled="busy" @click="load">捨棄輸入並重新讀取</button></div></div>
    <form @submit.prevent="save"><label for="local-checkpoint-paths">額外 checkpoint 目錄（每行一個，最多 8 個）</label><textarea id="local-checkpoint-paths" aria-describedby="local-paths-help" v-model="text" :disabled="busy || !data" rows="5" maxlength="32775" spellcheck="false" placeholder="D:\AI\Models\checkpoints&#10;E:\Shared Models\checkpoints"></textarea>
      <p id="local-paths-help" class="footnote">請填寫平台主機上已存在且可讀取的絕對目錄。刪除對應行即可移除此處登記；留空表示不追加本平台的目錄，ComfyUI 原有搜尋範圍仍保留。</p>
      <div class="paths-actions"><button class="primary" :disabled="busy || !data || !dirty || conflict">{{ busy ? '處理中…' : '保存模型目錄' }}</button><span class="muted">{{ pathCount }} / 8 個額外目錄 · {{ dirty ? '尚未保存' : '與保存設定一致' }}</span></div>
    </form>
    <template v-if="data">
      <p class="footnote">已保存修訂 {{ data.revision }} · {{ updatedAt }} · 執行中引擎的套用狀態：未確認。</p>
      <p class="restart-note">保存後需手動停止 ComfyUI，再使用 start-comfyui.ps1 重新啟動，最後到模型庫同步清單。</p>
      <details class="directory-details"><summary>已保存目錄與磁碟狀態</summary>
        <div class="directory-card"><div class="directory-heading"><h3>預設 checkpoint 目錄</h3><span :class="{ unavailable: data.default_directory.status !== 'existing' }">{{ directoryStatus(data.default_directory.status) }}</span></div><code>{{ data.default_directory.path }}</code>
          <p class="footnote">ComfyUI 原有預設目錄，固定保留。</p><dl><dt>磁碟總量</dt><dd>{{ diskSize(data.default_directory.disk?.total) }}</dd><dt>磁碟可用</dt><dd>{{ diskSize(data.default_directory.disk?.free) }}</dd></dl><p v-if="data.default_directory.error" class="directory-error">{{ data.default_directory.error }}</p></div>
        <div v-for="(directory, index) in data.directories" :key="directory.path + index" class="directory-card"><div class="directory-heading"><h3>額外目錄 {{ index + 1 }}</h3><span :class="{ unavailable: directory.status !== 'existing' }">{{ directoryStatus(directory.status) }}</span></div><code>{{ directory.path }}</code>
          <p class="footnote">追加順序 {{ index + 1 }}</p><dl><dt>磁碟總量</dt><dd>{{ diskSize(directory.disk?.total) }}</dd><dt>磁碟可用</dt><dd>{{ diskSize(directory.disk?.free) }}</dd></dl><p v-if="directory.error" class="directory-error">{{ directory.error }}</p></div>
        <p v-if="!data.directories.length" class="footnote">尚無額外目錄。</p>
        <p class="footnote">保留 ComfyUI 原有搜尋順序，再依登記順序由上到下追加。同一相對檔名重複時，最先找到的檔案優先；既有目錄設定可能先於此處，建議使用可區分的檔名。</p>
        <p class="footnote">容量屬於目錄所在磁碟；無法取得時顯示未知。模型庫清單不代表 checkpoint 的來源路徑或權重已驗證。</p>
      </details>
      <ul v-if="data.warnings.length" class="directory-warnings"><li v-for="(warning, index) in data.warnings" :key="index">{{ warning }}</li></ul>
    </template>
  </article>
</template>

<style scoped>
.local-model-paths{max-width:900px}.paths-heading{display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap}.paths-heading h2{margin-top:16px}.local-model-paths p{font-size:12px}.local-model-paths .footnote{font-size:10px}.local-model-paths code{font-family:monospace;overflow-wrap:anywhere;color:#b8cdb1}.scope-note{padding:12px;background:#202b24;border-radius:7px}.local-model-paths label{display:block;font-size:12px;margin:24px 0 10px}.local-model-paths textarea{width:100%;padding:13px;background:var(--surface-input);color:var(--text-primary);border:1px solid var(--border-control);border-radius:7px;font-family:monospace;font-size:12px;line-height:1.8;resize:vertical}.local-model-paths textarea:focus-visible{outline:2px solid var(--focus-ring);outline-offset:3px}.paths-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:14px}.paths-actions .muted{font-size:11px}.restart-note{color:#c4d9b8}.directory-details{border-top:1px solid #35403a;padding-top:18px;margin-top:22px;font-size:12px}.directory-details summary{cursor:pointer;color:#c4d9b8}.directory-card{border:1px solid #35403a;border-radius:7px;padding:14px;margin-top:14px}.directory-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}.directory-heading h3{font-size:12px;margin:0}.directory-heading span{font-size:10px;color:#b8d4aa}.directory-heading .unavailable,.directory-error{color:#ebc4a1}.directory-card dl{display:grid;grid-template-columns:auto 1fr;gap:8px 16px;font-size:11px}.directory-card dt{color:#8e9e96}.directory-card dd{margin:0}.directory-warnings{font-size:11px;line-height:1.8;padding-left:20px;color:#b7aa94}.success{border-color:#53674b;background:#26332a;color:#cee0c4}@media(max-width:700px){.paths-heading{align-items:start}.directory-heading{align-items:start;flex-direction:column}}
</style>
