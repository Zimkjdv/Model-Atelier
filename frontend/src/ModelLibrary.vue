<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ModelValidation from './ModelValidation.vue'
import { architectures, architectureLabel, fileHash, fileSize, metadataTime, parseFileSize, safeMetadataUrl, validArchitecture } from './modelMetadata'
import type { Architecture, ModelMetadata } from './modelMetadata'
type Model = ModelMetadata & { name: string; listed: boolean; notes: string; source_url: string; version?: string }
type Engine = { connected: boolean; url: string; stats?: { system?: { comfyui_version?: string } } }
type Catalog = { engine_url: string; models: Model[]; selected: string | null; synced_at: string | null; sync_error: string | null }
const emit = defineEmits<{ settings: [] }>()
const catalog = ref<Catalog | null>(null), search = ref(''), filter = ref('all')
const busy = ref(false), error = ref(''), feedback = ref('')
const editing = ref<string | null>(null), notes = ref(''), source = ref('')
const version = ref(''), engine = ref<Engine | null>(null)
const validationName = ref('')
const validationModel = computed(() => catalog.value?.models.find(model => model.name === validationName.value))
const architecture = ref<Architecture>('unknown'), sizeBytes = ref(''), sha256 = ref('')
const licenseName = ref(''), licenseUrl = ref('')
const engineVersion = computed(() => {
  const value = engine.value?.stats?.system?.comfyui_version
  return engine.value?.connected && engine.value.url === catalog.value?.engine_url && typeof value === 'string' && value.trim() ? value : '未知'
})
async function refreshEngine() {
  engine.value = null
  try {
    const response = await fetch('/api/engine')
    if (response.ok) engine.value = await response.json()
  } catch { /* An unavailable engine has an unknown version. */ }
}
const visible = computed(() => (catalog.value?.models ?? []).filter(model =>
  model.name.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()) &&
  (filter.value === 'all' || (filter.value === 'listed' ? model.listed : !model.listed))))
async function request(path: string, method = 'GET', body?: unknown) {
  const response = await fetch('/api/models' + path, { method,
    ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : '資料格式不正確，請檢查來源網址及欄位長度。')
  }
  return response.json() as Promise<Catalog>
}
async function load(sync = false) {
  if (busy.value) return
  busy.value = true; error.value = ''; feedback.value = ''
  try {
    const next = await request(sync ? '/sync' : '', sync ? 'POST' : 'GET')
    catalog.value = sync ? await request('') : next
    await refreshEngine()
    if (sync && !catalog.value.sync_error && catalog.value.engine_url === next.engine_url)
      feedback.value = '清單已同步。模型尚未載入 GPU。'
  } catch { error.value = '無法讀取模型庫，請確認平台後端已啟動。原有畫面可能已過期。' }
  finally { busy.value = false }
}
function edit(model: Model) {
  editing.value = model.name; notes.value = model.notes; source.value = model.source_url; version.value = model.version ?? ''
  architecture.value = validArchitecture(model.architecture)
  sizeBytes.value = typeof model.size_bytes === 'number' && Number.isSafeInteger(model.size_bytes) && model.size_bytes > 0 ? String(model.size_bytes) : ''
  sha256.value = fileHash(model.sha256) === '未知' ? '' : model.sha256 ?? ''
  licenseName.value = model.license_name ?? ''; licenseUrl.value = model.license_url ?? ''
  feedback.value = ''; error.value = ''
}
async function update(model: Model, metadata = false) {
  if (busy.value || !catalog.value) return
  busy.value = true; error.value = ''; feedback.value = ''
  try {
    const metadataValues = metadata ? {
      notes: notes.value, source_url: source.value, version: version.value,
      architecture: architecture.value, size_bytes: parseFileSize(sizeBytes.value),
      sha256: sha256.value.trim().toLowerCase(), license_name: licenseName.value,
      license_url: licenseUrl.value,
    } : {}
    if (metadata && metadataValues.sha256 && !/^[a-f0-9]{64}$/.test(metadataValues.sha256))
      throw new Error('模型 SHA-256 請填入完整的 64 位十六進位值，或留空表示未知。')
    catalog.value = await request(metadata ? '/metadata' : '/selection', 'PUT', {
      engine_url: catalog.value.engine_url, name: model.name,
      ...metadataValues,
    })
    if (metadata) editing.value = null
    feedback.value = metadata ? '模型資料已保存。' : '偏好模型已保存；此操作不會載入或執行模型。'
  } catch (e) { error.value = e instanceof Error ? e.message : '保存失敗' }
  finally { busy.value = false }
}
onMounted(() => load())
</script>

<template>
  <div class="library">
    <div class="panel library-intro">
      <div><span class="chip">CHECKPOINT LIBRARY</span><h2>你的模型，一目了然</h2>
        <p>讀取 ComfyUI 已登記的 checkpoint，整理版本、架構、檔案資訊與來源。</p>
        <code>{{ catalog?.engine_url ?? '正在讀取執行引擎…' }}</code></div>
      <div class="library-actions"><button class="primary" :disabled="busy || editing !== null" @click="load(true)">{{ busy ? '處理中…' : '↻ 同步模型清單' }}</button><button class="secondary" @click="emit('settings')">連線設定</button></div>
    </div>
    <article class="panel engine-version">
      <div class="panel-heading"><h2>ComfyUI 執行引擎</h2><span class="chip">版本 {{ engineVersion }}</span></div>
      <p>版本來源：{{ engineVersion === '未知' ? '尚未取得有效的服務版本回報' : '目前連接的 ComfyUI /system_stats 回報' }}</p>
      <a class="source-link" href="https://github.com/Comfy-Org/ComfyUI" target="_blank" rel="noopener noreferrer">官方專案來源：GitHub / Comfy-Org / ComfyUI ↗</a>
      <p class="footnote">此為引擎版本，並非 checkpoint 版本。顯示目前服務回報的版本，不以 GitHub 最新版代替；官方專案連結不表示遠端服務必定使用未修改的官方程式。</p>
    </article>
    <p v-if="error" role="alert" class="notice warning">{{ error }} <button class="secondary" :disabled="busy || editing !== null" @click="load()">重新載入</button></p>
    <p v-if="catalog?.sync_error" role="alert" class="notice warning">{{ catalog.sync_error }} 此處顯示的是歷史紀錄，不代表模型目前可用。</p>
    <p v-if="feedback" role="status" class="notice success">{{ feedback }}</p>
    <div class="library-toolbar">
      <label class="search-label">搜尋模型<input v-model="search" type="search" placeholder="輸入 checkpoint 檔名"></label>
      <label>清單狀態<select v-model="filter"><option value="all">全部紀錄</option><option value="listed">最近清單內</option><option value="missing">最近清單未列出</option></select></label>
      <span class="muted" role="status">{{ visible.length }} 個模型</span>
    </div>
    <p class="footnote">{{ catalog?.synced_at ? '最後成功同步：' + new Date(catalog.synced_at).toLocaleString() : '尚未成功同步' }} · 清單狀態為同步時的快照，並非即時可用性或架構相容性驗證。</p>
    <p class="footnote">以下為使用者登記資料，不代表平台已核對對應檔案、完整授權條款或流程相容性。</p>
    <article v-if="!catalog && busy" class="panel placeholder" role="status"><h2>正在讀取模型紀錄…</h2></article>
    <article v-else-if="!catalog?.models.length" class="panel placeholder"><span class="outline-icon">▦</span><h2>{{ catalog?.synced_at ? 'ComfyUI 尚未列出 checkpoint' : '建立你的第一份模型清單' }}</h2><p>先啟動 ComfyUI 並確認其中已登記 checkpoint，<br>再按「同步模型清單」。平台不會自動下載模型。</p></article>
    <article v-else-if="!visible.length" class="panel placeholder"><h2>沒有符合條件的模型</h2><button class="secondary" @click="search = ''; filter = 'all'">清除篩選</button></article>
    <div class="model-grid">
      <article v-for="model in visible" :key="model.name" class="panel model-card" :class="{ preferred: catalog?.selected === model.name }">
        <div class="model-card-top"><span class="chip">CHECKPOINT</span><span class="status" :class="{ connected: model.listed }">{{ model.listed ? '最近清單內' : '最近清單未列出' }}</span></div>
        <h2>{{ model.name }}</h2><p class="footnote">登記架構：{{ architectureLabel(model.architecture) }}</p>
        <p>模型版本：{{ model.version?.trim() || '未知' }}<span v-if="model.version?.trim()" class="muted">（使用者登記）</span></p>
        <p class="footnote">檔案大小：{{ fileSize(model.size_bytes) }}</p>
        <p v-if="!safeMetadataUrl(model.source_url)" class="footnote">模型來源：未知</p>
        <form v-if="editing === model.name" class="model-form" @submit.prevent="update(model, true)">
          <label :for="'version-' + model.name">模型版本</label><input :id="'version-' + model.name" v-model="version" maxlength="100" placeholder="未填寫時顯示未知">
          <label :for="'architecture-' + model.name">模型架構（使用者登記）</label><select :id="'architecture-' + model.name" v-model="architecture"><option v-for="option in architectures" :key="option.value" :value="option.value">{{ option.label }}</option></select>
          <label :for="'size-' + model.name">檔案大小（bytes）</label><input :id="'size-' + model.name" v-model="sizeBytes" inputmode="numeric" maxlength="16" placeholder="正整數；留空表示未知">
          <label :for="'hash-' + model.name">模型檔案 SHA-256</label><input aria-describedby="model-hash-help" :id="'hash-' + model.name" v-model="sha256" maxlength="64" autocomplete="off" spellcheck="false" placeholder="完整 64 位十六進位值；留空表示未知"><p id="model-hash-help" class="footnote">請填完整 64 位十六進位 SHA256；留空為未知，登記不代表已驗證檔案。</p>
          <label :for="'source-' + model.name">來源網址</label><input :id="'source-' + model.name" v-model="source" type="url" maxlength="2048" placeholder="https://…">
          <label :for="'license-name-' + model.name">授權名稱／標記</label><input :id="'license-name-' + model.name" v-model="licenseName" maxlength="200" placeholder="依上游登記；留空表示未知">
          <label :for="'license-url-' + model.name">授權條款網址</label><input :id="'license-url-' + model.name" v-model="licenseUrl" type="url" maxlength="2048" placeholder="https://…">
          <label :for="'notes-' + model.name">備註</label><textarea :id="'notes-' + model.name" v-model="notes" maxlength="4000" rows="4" placeholder="版本、用途、授權說明或待驗證事項"></textarea>
          <div class="library-actions"><button class="primary" :disabled="busy">保存資料</button><button type="button" class="secondary" :disabled="busy" @click="editing = null">取消</button></div>
        </form>
        <template v-else>
          <p class="model-notes">{{ model.notes || '尚未加入備註。' }}</p>
          <a v-if="safeMetadataUrl(model.source_url)" :href="safeMetadataUrl(model.source_url)" target="_blank" rel="noopener noreferrer" class="source-link">查看登記來源 ↗</a>
          <details class="metadata-details"><summary>檔案識別與授權資料</summary><dl>
            <dt>模型檔案 SHA-256</dt><dd class="file-hash">{{ fileHash(model.sha256) }}</dd>
            <dt>授權名稱／標記</dt><dd>{{ model.license_name?.trim() || '未知' }}</dd>
            <dt>授權條款網址</dt><dd><a v-if="safeMetadataUrl(model.license_url)" :href="safeMetadataUrl(model.license_url)" target="_blank" rel="noopener noreferrer" class="source-link">查看登記條款 ↗</a><span v-else>未知</span></dd>
            <dt>資料最後更新</dt><dd>{{ metadataTime(model.metadata_updated_at) }}</dd>
          </dl></details>
          <button type="button" class="secondary" @click="validationName = validationName === model.name ? '' : model.name">{{ validationName === model.name ? '收合驗證紀錄' : '查看流程驗證紀錄' }}</button>
          <ModelValidation v-if="validationName === model.name && catalog" :engine-url="catalog.engine_url" :name="model.name" :refresh-key="validationModel?.metadata_updated_at || ''" />
          <div class="model-footer"><button class="secondary" :disabled="busy || editing !== null" @click="edit(model)">編輯資料</button><button class="primary" :disabled="busy || !model.listed || editing !== null || catalog?.selected === model.name" @click="update(model)">{{ catalog?.selected === model.name ? '✓ 偏好模型' : '設為偏好' }}</button></div>
        </template>
      </article>
    </div>
  </div>
</template>

<style scoped>
.library-intro{display:flex;justify-content:space-between;align-items:center;gap:24px;background:linear-gradient(115deg,#26332a,#191d20)}
.library-intro h2{font-size:23px;margin-top:20px}.library-intro code{color:#9eb29f;font-size:12px;overflow-wrap:anywhere}
.metadata-details{margin-top:18px;font-size:12px}.metadata-details summary{cursor:pointer;color:#c0d4b4}.metadata-details dl{display:grid;gap:10px;margin-top:18px}.metadata-details dt{color:#9fb1a5}.metadata-details dd{margin:0;overflow-wrap:anywhere}.file-hash{font-family:monospace;line-height:1.7}.model-form input,.model-form select{min-width:0;width:100%;box-sizing:border-box}
.library-actions{display:flex;gap:10px;flex-wrap:wrap}.library-toolbar{display:flex;gap:20px;align-items:end;margin-top:28px}.library-toolbar label{display:grid;gap:9px;font-size:12px}.search-label{flex:1}.library-toolbar .muted{font-size:12px;padding-bottom:14px;white-space:nowrap}select,textarea{font:inherit;background:var(--surface-input);color:var(--text-primary);border:1px solid var(--border-control);border-radius:7px;padding:13px}textarea{width:100%;resize:vertical}select:focus-visible,textarea:focus-visible{outline:2px solid var(--focus-ring);outline-offset:3px}.model-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.model-card{margin:0;min-width:0}.model-card.preferred{border-color:#8aab7d}.model-card-top{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}.model-card h2{margin-top:22px;line-height:1.6;overflow-wrap:anywhere}.model-notes{white-space:pre-wrap;overflow-wrap:anywhere;min-height:40px}.model-footer{display:flex;justify-content:space-between;gap:12px;border-top:1px solid #30363a;padding-top:18px;margin-top:20px}.source-link{color:#c0d4b4;font-size:12px}.model-form{display:grid;gap:12px;font-size:12px}.success{border-color:#53674b;background:#26332a;color:#cee0c4}@media(max-width:1000px){.library-intro{align-items:start;flex-direction:column}.model-grid{grid-template-columns:1fr}}@media(max-width:700px){.library-toolbar{flex-wrap:wrap;gap:12px}.search-label{flex-basis:100%}.library-toolbar .muted{margin-left:auto}.model-footer{flex-wrap:wrap}}
</style>
