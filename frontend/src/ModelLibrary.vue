<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
type Model = { name: string; listed: boolean; notes: string; source_url: string; version?: string }
type Engine = { connected: boolean; url: string; stats?: { system?: { comfyui_version?: string } } }
type Catalog = { engine_url: string; models: Model[]; selected: string | null; synced_at: string | null; sync_error: string | null }
const emit = defineEmits<{ settings: [] }>()
const catalog = ref<Catalog | null>(null), search = ref(''), filter = ref('all')
const busy = ref(false), error = ref(''), feedback = ref('')
const editing = ref<string | null>(null), notes = ref(''), source = ref('')
const version = ref(''), engine = ref<Engine | null>(null)
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
  feedback.value = ''; error.value = ''
}
async function update(model: Model, metadata = false) {
  if (busy.value || !catalog.value) return
  busy.value = true; error.value = ''; feedback.value = ''
  try {
    catalog.value = await request(metadata ? '/metadata' : '/selection', 'PUT', {
      engine_url: catalog.value.engine_url, name: model.name,
      ...(metadata ? { notes: notes.value, source_url: source.value, version: version.value } : {}),
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
        <p>讀取 ComfyUI 已登記的 checkpoint，整理來源與備註。模型檔案留在原本的位置。</p>
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
      <span class="muted">{{ visible.length }} 個模型</span>
    </div>
    <p class="footnote">{{ catalog?.synced_at ? '最後成功同步：' + new Date(catalog.synced_at).toLocaleString() : '尚未成功同步' }} · 清單狀態為同步時的快照，並非即時可用性或架構相容性驗證。</p>
    <article v-if="!catalog && busy" class="panel placeholder"><h2>正在讀取模型紀錄…</h2></article>
    <article v-else-if="!catalog?.models.length" class="panel placeholder"><span class="outline-icon">▦</span><h2>{{ catalog?.synced_at ? 'ComfyUI 尚未列出 checkpoint' : '建立你的第一份模型清單' }}</h2><p>先啟動 ComfyUI 並確認其中已登記 checkpoint，<br>再按「同步模型清單」。平台不會自動下載模型。</p></article>
    <article v-else-if="!visible.length" class="panel placeholder"><h2>沒有符合條件的模型</h2><button class="secondary" @click="search = ''; filter = 'all'">清除篩選</button></article>
    <div class="model-grid">
      <article v-for="model in visible" :key="model.name" class="panel model-card" :class="{ preferred: catalog?.selected === model.name }">
        <div class="model-card-top"><span class="chip">CHECKPOINT</span><span class="status" :class="{ connected: model.listed }">{{ model.listed ? '最近清單內' : '最近清單未列出' }}</span></div>
        <h2>{{ model.name }}</h2><p class="footnote">架構與相容性：未驗證</p>
        <p>模型版本：{{ model.version?.trim() || '未知' }}<span v-if="model.version?.trim()" class="muted">（使用者登記）</span></p>
        <p v-if="!model.source_url" class="footnote">模型來源：未知</p>
        <form v-if="editing === model.name" class="model-form" @submit.prevent="update(model, true)">
          <label :for="'version-' + model.name">模型版本</label><input :id="'version-' + model.name" v-model="version" maxlength="100" placeholder="未填寫時顯示未知">
          <label :for="'source-' + model.name">來源網址</label><input :id="'source-' + model.name" v-model="source" type="url" maxlength="2048" placeholder="https://…">
          <label :for="'notes-' + model.name">備註</label><textarea :id="'notes-' + model.name" v-model="notes" maxlength="4000" rows="4" placeholder="版本、用途、授權說明或待驗證事項"></textarea>
          <div class="library-actions"><button class="primary" :disabled="busy">保存資料</button><button type="button" class="secondary" :disabled="busy" @click="editing = null">取消</button></div>
        </form>
        <template v-else><p class="model-notes">{{ model.notes || '尚未加入備註。' }}</p><a v-if="model.source_url" :href="model.source_url" target="_blank" rel="noopener noreferrer" class="source-link">查看登記來源 ↗</a><div class="model-footer"><button class="secondary" :disabled="busy || editing !== null" @click="edit(model)">編輯資料</button><button class="primary" :disabled="busy || !model.listed || editing !== null || catalog?.selected === model.name" @click="update(model)">{{ catalog?.selected === model.name ? '✓ 偏好模型' : '設為偏好' }}</button></div></template>
      </article>
    </div>
  </div>
</template>

<style scoped>
.library-intro{display:flex;justify-content:space-between;align-items:center;gap:24px;background:linear-gradient(115deg,#26332a,#191d20)}
.library-intro h2{font-size:23px;margin-top:20px}.library-intro code{color:#9eb29f;font-size:12px;overflow-wrap:anywhere}
.library-actions{display:flex;gap:10px;flex-wrap:wrap}.library-toolbar{display:flex;gap:20px;align-items:end;margin-top:28px}.library-toolbar label{display:grid;gap:9px;font-size:12px}.search-label{flex:1}.library-toolbar .muted{font-size:12px;padding-bottom:14px;white-space:nowrap}select,textarea{font:inherit;background:#101517;color:#e5ebe7;border:1px solid #4c5855;border-radius:7px;padding:13px}textarea{width:100%;resize:vertical}select:focus-visible,textarea:focus-visible{outline:2px solid #adceb0;outline-offset:3px}.model-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.model-card{margin:0;min-width:0}.model-card.preferred{border-color:#8aab7d}.model-card-top{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}.model-card h2{margin-top:22px;line-height:1.6;overflow-wrap:anywhere}.model-notes{white-space:pre-wrap;overflow-wrap:anywhere;min-height:40px}.model-footer{display:flex;justify-content:space-between;gap:12px;border-top:1px solid #30363a;padding-top:18px;margin-top:20px}.source-link{color:#c0d4b4;font-size:12px}.model-form{display:grid;gap:12px;font-size:12px}.success{border-color:#53674b;background:#26332a;color:#cee0c4}@media(max-width:1000px){.library-intro{align-items:start;flex-direction:column}.model-grid{grid-template-columns:1fr}}@media(max-width:700px){.library-toolbar{flex-wrap:wrap;gap:12px}.search-label{flex-basis:100%}.library-toolbar .muted{margin-left:auto}.model-footer{flex-wrap:wrap}}
</style>
