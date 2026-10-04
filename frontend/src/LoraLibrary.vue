<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import LoraValidation from './LoraValidation.vue'
import { architectures, architectureLabel, fileHash, fileSize, metadataTime, parseFileSize, safeMetadataUrl, validArchitecture } from './modelMetadata'
import type { Architecture, ModelMetadata } from './modelMetadata'

type Lora = ModelMetadata & { name: string; listed: boolean; version: string; notes: string; source_url: string }
type Catalog = { engine_url: string; loras: Lora[]; synced_at: string | null; sync_error: string | null }
type Checkpoint = ModelMetadata & { name: string; listed: boolean }
type AssessedRecord = { name: string; architecture: Architecture; listed: boolean; metadata_updated_at: string | null }
type Compatibility = AssessedRecord & { status: 'compatible' | 'unverified' | 'incompatible'; label: string; message: string; verified: false }
type Assessment = { engine_url: string; checkpoint: AssessedRecord; loras: Compatibility[];
  source: 'registered_architecture'; workflow_supported: boolean; assessed_at: string;
  lora_synced_at: string | null; lora_sync_error: string | null }
const props = defineProps<{ engineUrl: string; checkpoints: Checkpoint[]; preferredCheckpoint: string | null }>()
const catalog = ref<Catalog | null>(null), busy = ref(false), error = ref(''), feedback = ref('')
const search = ref(''), filter = ref('all'), editing = ref<string | null>(null)
const version = ref(''), architecture = ref<Architecture>('unknown'), source = ref(''), notes = ref('')
const sizeBytes = ref(''), sha256 = ref(''), licenseName = ref(''), licenseUrl = ref('')
let revision = 0
const checkpointChoice = ref(''), assessment = ref<Assessment | null>(null)
const evidenceName = ref('')
const assessing = ref(false), assessmentError = ref('')
let assessmentRevision = 0
const compared = computed(() => new Map(assessment.value?.loras.map(item => [item.name, item]) ?? []))
const assessmentCounts = computed(() => assessment.value ? ['compatible', 'unverified', 'incompatible'].map(status =>
  assessment.value!.loras.filter(item => item.status === status).length) : null)
const visible = computed(() => (catalog.value?.loras ?? []).filter(item =>
  item.name.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()) &&
  (filter.value === 'all' || (filter.value === 'listed' ? item.listed : !item.listed))))
async function request(path = '', method = 'GET', body?: unknown): Promise<Catalog> {
  const response = await fetch('/api/loras' + path, { method,
    ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'LoRA 資料無效，請檢查網址、SHA256 及欄位長度。')
  if (data.engine_url !== props.engineUrl || !Array.isArray(data.loras))
    throw new Error('引擎設定已變更，請重新載入模型庫；目前輸入仍保留。')
  return data
}
async function checkCompatibility() {
  const ticket = ++assessmentRevision
  assessment.value = null; assessmentError.value = ''; assessing.value = false
  const snapshot = catalog.value, checkpoint = props.checkpoints.find(item => item.name === checkpointChoice.value)
  if (!snapshot || snapshot.engine_url !== props.engineUrl || !checkpoint) return
  assessing.value = true
  try {
    const params = new URLSearchParams({ engine_url: props.engineUrl, checkpoint: checkpoint.name })
    const response = await fetch('/api/loras/compatibility?' + params)
    const data: Assessment = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = (data as unknown as { detail?: unknown }).detail
      throw new Error(typeof detail === 'string' ? detail : '無法讀取 LoRA 相容性，請重新讀取模型庫。')
    }
    if (ticket !== assessmentRevision) return
    const sameRecord = (incoming: AssessedRecord, original: Checkpoint) => incoming &&
      incoming.name === original.name && incoming.architecture === validArchitecture(original.architecture) &&
      incoming.listed === original.listed && incoming.metadata_updated_at === (original.metadata_updated_at ?? null)
    const registered = new Map(snapshot.loras.map(item => [item.name, item]))
    if (!data || data.engine_url !== props.engineUrl || data.source !== 'registered_architecture' || typeof data.workflow_supported !== 'boolean' ||
        !sameRecord(data.checkpoint, checkpoint) || data.lora_synced_at !== snapshot.synced_at ||
        data.lora_sync_error !== snapshot.sync_error || !Array.isArray(data.loras) || data.loras.length !== snapshot.loras.length ||
        new Set(data.loras.map(item => item.name)).size !== data.loras.length || !data.loras.every(item => {
          const original = registered.get(item.name)
          return original && sameRecord(item, original) && item.verified === false &&
            ['compatible', 'unverified', 'incompatible'].includes(item.status) &&
            typeof item.label === 'string' && typeof item.message === 'string'
        })) throw new Error('登記資料已更新或回覆不一致，請按「重新讀取模型庫」後再比較；原有編輯輸入仍保留。')
    assessment.value = data
  } catch (e) { if (ticket === assessmentRevision) assessmentError.value = e instanceof Error ? e.message : '相容性查詢失敗。' }
  finally { if (ticket === assessmentRevision) assessing.value = false }
}
async function load(sync = false) {
  if (busy.value) return
  const ticket = revision, engineUrl = props.engineUrl
  busy.value = true; error.value = ''; feedback.value = ''
  try {
    const next = await request(sync ? '/sync' : '', sync ? 'POST' : 'GET', sync ? { engine_url: engineUrl } : undefined)
    if (ticket !== revision) return
    catalog.value = next
    if (sync && !next.sync_error) feedback.value = 'LoRA 清單已同步；尚未載入或驗證權重。'
  } catch (e) { if (ticket === revision) error.value = e instanceof Error ? e.message : 'LoRA 模型庫讀取失敗。' }
  finally { if (ticket === revision) busy.value = false }
}
function edit(item: Lora) {
  editing.value = item.name; version.value = item.version; architecture.value = validArchitecture(item.architecture)
  source.value = item.source_url; notes.value = item.notes; licenseName.value = item.license_name ?? ''; licenseUrl.value = item.license_url ?? ''
  sizeBytes.value = fileSize(item.size_bytes) === '未知' ? '' : String(item.size_bytes)
  sha256.value = fileHash(item.sha256) === '未知' ? '' : item.sha256 ?? ''
  error.value = ''; feedback.value = ''
}
async function save() {
  if (busy.value || !catalog.value || !editing.value) return
  const ticket = revision
  busy.value = true; error.value = ''; feedback.value = ''
  try {
    const hash = sha256.value.trim().toLowerCase()
    if (hash && !/^[a-f0-9]{64}$/.test(hash)) throw new Error('SHA256 請填完整 64 位十六進位值，或留空表示未知。')
    const next = await request('/metadata', 'PUT', { engine_url: catalog.value.engine_url, name: editing.value,
      version: version.value, architecture: architecture.value, source_url: source.value, notes: notes.value,
      size_bytes: parseFileSize(sizeBytes.value), sha256: hash, license_name: licenseName.value, license_url: licenseUrl.value })
    if (ticket !== revision) return
    catalog.value = next; editing.value = null; feedback.value = 'LoRA 登記資料已保存。'
  } catch (e) { if (ticket === revision) error.value = e instanceof Error ? e.message : '保存失敗，輸入仍保留。' }
  finally { if (ticket === revision) busy.value = false }
}
watch(() => props.engineUrl, () => {
  revision++; catalog.value = null; editing.value = null; busy.value = false; error.value = ''; feedback.value = ''
  void load()
}, { immediate: true })
watch(() => [props.engineUrl, JSON.stringify(props.checkpoints), props.preferredCheckpoint], (next, previous) => {
  const previousChoice = checkpointChoice.value
  if (!previous || next[0] !== previous[0] || !props.checkpoints.some(item => item.name === previousChoice))
    checkpointChoice.value = props.checkpoints.some(item => item.name === props.preferredCheckpoint) ? props.preferredCheckpoint! : ''
  if (checkpointChoice.value === previousChoice) void checkCompatibility()
}, { immediate: true })
watch(checkpointChoice, () => { void checkCompatibility() })
watch(catalog, () => { void checkCompatibility() })
</script>

<template>
  <section class="lora-library" aria-labelledby="lora-heading">
    <div class="panel lora-intro">
      <div><span class="chip">LORA LIBRARY</span><h2 id="lora-heading">LoRA 模型庫</h2><p>整理引擎登記的 LoRA 及基礎架構，保存版本與來源。</p></div>
      <button type="button" class="primary" :disabled="busy || editing !== null" @click="load(true)">{{ busy ? '處理中…' : '同步 LoRA 清單' }}</button>
    </div>
    <p class="footnote">{{ engineUrl }} · {{ catalog?.synced_at ? '最後成功同步：' + metadataTime(catalog.synced_at) : '尚未成功同步' }}</p>
    <p class="footnote">清單及資料為登記快照；未核對實際檔案。創作頁可有序選擇最多四個不同 LoRA，生成前逐個重新檢查；單一組合實測不涵蓋多 LoRA 或其他畫風。</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }} <button class="secondary" :disabled="busy || editing !== null" @click="load()">重新讀取 LoRA</button></p>
    <p v-if="catalog?.sync_error" class="notice warning" role="alert">{{ catalog.sync_error }} 此處保留歷史清單，不代表目前可用。</p>
    <p v-if="feedback" class="notice success" role="status">{{ feedback }}</p>
    <div class="panel lora-assessment">
      <h3>比較 checkpoint 與 LoRA</h3>
      <p class="footnote" id="lora-assessment-help">只比較使用者登記架構，無法保證權重、基礎模型或 GPU 可載入；檔名及版本文字不影響判定。選擇只供查看，不改變偏好模型或創作設定。</p>
      <label>比較用 checkpoint<select v-model="checkpointChoice" aria-describedby="lora-assessment-help"><option value="">請選擇 checkpoint</option><option v-for="item in checkpoints" :key="item.name" :value="item.name">{{ item.name }} · {{ architectureLabel(item.architecture) }}{{ item.listed ? '' : ' · 最近未列出' }}</option></select></label>
      <button type="button" class="secondary" :disabled="assessing || busy || editing !== null || !checkpointChoice" @click="load()">更新 LoRA 相容性</button>
      <p v-if="assessing" role="status" class="footnote">正在比較登記架構…</p>
      <p v-else-if="assessmentError" role="alert" class="notice warning">{{ assessmentError }}</p>
      <p v-else-if="assessment && assessmentCounts" role="status" class="footnote">架構相容 {{ assessmentCounts[0] }} · 未驗證 {{ assessmentCounts[1] }} · 不相容 {{ assessmentCounts[2] }}（只比較登記架構）<br>比較：{{ assessment.checkpoint.name }} · {{ metadataTime(assessment.assessed_at) }}</p>
      <p v-else class="footnote">選擇 checkpoint 後會顯示 LoRA 的架構比較結果。</p>
    </div>
    <div class="lora-toolbar">
      <label>搜尋 LoRA<input v-model="search" type="search" placeholder="輸入 LoRA 名稱"></label>
      <label>LoRA 清單狀態<select v-model="filter"><option value="all">全部紀錄</option><option value="listed">最近清單內</option><option value="missing">最近清單未列出</option></select></label>
      <span class="muted" role="status">{{ visible.length }} 個 LoRA</span>
    </div>
    <article v-if="!catalog && busy" class="panel" role="status">正在讀取 LoRA…</article>
    <article v-else-if="catalog && !catalog.loras.length" class="panel"><h3>尚無 LoRA 登記</h3><p>將已有的 LoRA 放入 ComfyUI 的 loras 目錄或其額外路徑，啟動引擎後同步。平台不會自動下載模型。</p></article>
    <p v-else-if="catalog && !visible.length" class="notice">沒有符合篩選的 LoRA。<button class="secondary" @click="search = ''; filter = 'all'">清除 LoRA 篩選</button></p>
    <div class="lora-grid">
      <article v-for="item in visible" :key="item.name" class="panel lora-card">
        <div class="lora-top"><span class="chip">LORA</span><span class="status" :class="{ connected: item.listed }">{{ item.listed ? '最近清單內' : '最近清單未列出' }}</span></div>
        <h3>{{ item.name }}</h3><p>版本：{{ item.version.trim() || '未知' }}</p><p class="footnote">登記基礎架構：{{ architectureLabel(item.architecture) }}</p>
        <template v-if="compared.get(item.name)">
          <p class="compatibility-label" :class="compared.get(item.name)!.status">{{ compared.get(item.name)!.label }}</p>
          <details class="compatibility-reason"><summary>相容性判定說明</summary><p class="footnote">{{ compared.get(item.name)!.message }}</p></details>
        </template>
        <p v-else class="footnote">{{ assessing ? '正在比較架構…' : checkpointChoice ? '相容性尚未取得' : '尚未選擇比較用 checkpoint' }}</p>
        <form v-if="editing === item.name" class="lora-form" @submit.prevent="save">
          <label>LoRA 版本<input v-model="version" maxlength="100" placeholder="留空表示未知"></label>
          <label>LoRA 基礎架構（使用者登記）<select v-model="architecture"><option v-for="option in architectures" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
          <label>LoRA 來源網址<input v-model="source" type="url" maxlength="2048" placeholder="https://…"></label>
          <label>LoRA 檔案大小（bytes）<input v-model="sizeBytes" inputmode="numeric" maxlength="16" placeholder="留空表示未知"></label>
          <label>LoRA SHA256<input v-model="sha256" aria-describedby="lora-hash-help" maxlength="64" autocomplete="off" spellcheck="false"></label>
          <p id="lora-hash-help" class="footnote">完整 64 位十六進位雜湊；登記不代表平台已驗證實際檔案。</p>
          <label>LoRA 授權名稱<input v-model="licenseName" maxlength="200"></label>
          <label>LoRA 授權網址<input v-model="licenseUrl" type="url" maxlength="2048" placeholder="https://…"></label>
          <label>LoRA 備註<textarea v-model="notes" rows="3" maxlength="4000"></textarea></label>
          <div class="lora-actions"><button class="primary" :disabled="busy">保存 LoRA 資料</button><button type="button" class="secondary" :disabled="busy" @click="editing = null">取消 LoRA 編輯</button></div>
        </form>
        <template v-else>
          <p class="lora-notes">{{ item.notes || '尚未加入備註。' }}</p>
          <a v-if="safeMetadataUrl(item.source_url)" :href="safeMetadataUrl(item.source_url)" target="_blank" rel="noopener noreferrer">查看 LoRA 登記來源 ↗</a><p v-else class="footnote">來源：未知</p>
          <details><summary>LoRA 檔案與授權資料</summary><dl>
            <dt>大小</dt><dd>{{ fileSize(item.size_bytes) }}</dd><dt>SHA256</dt><dd>{{ fileHash(item.sha256) }}</dd>
            <dt>授權名稱</dt><dd>{{ item.license_name?.trim() || '未知' }}</dd><dt>授權條款</dt><dd><a v-if="safeMetadataUrl(item.license_url)" :href="safeMetadataUrl(item.license_url)" target="_blank" rel="noopener noreferrer">查看 LoRA 登記條款 ↗</a><span v-else>未知</span></dd>
            <dt>登記更新時間</dt><dd>{{ metadataTime(item.metadata_updated_at) }}</dd>
          </dl></details>
          <button type="button" class="secondary" :disabled="busy || editing !== null" @click="edit(item)">編輯 LoRA 資料</button>
          <button type="button" class="secondary" :disabled="!checkpointChoice || busy" @click="evidenceName = evidenceName === item.name ? '' : item.name">{{ evidenceName === item.name ? '收合組合實測' : '查看組合實測' }}</button>
          <LoraValidation v-if="evidenceName === item.name && checkpointChoice" :engine-url="engineUrl" :checkpoint="checkpointChoice" :lora="{ name: item.name, enabled: true, strength_model: 1, strength_clip: 1 }" :refresh-key="JSON.stringify([item.metadata_updated_at, checkpoints.find(v => v.name === checkpointChoice)?.metadata_updated_at, catalog?.synced_at])" />
        </template>
      </article>
    </div>
  </section>
</template>

<style scoped>
.lora-assessment h3{margin-top:0}.lora-assessment label{display:grid;gap:8px;font-size:12px;margin-bottom:14px}.lora-assessment select{min-width:0;width:100%;padding:12px;box-sizing:border-box}.compatibility-label{border:1px solid var(--border-notice);border-radius:var(--radius-control);padding:10px 12px;font-size:12px;background:var(--surface-notice);color:var(--text-notice)}.compatibility-label.unverified{color:var(--text-muted);background:var(--surface-input);border-color:var(--border-control)}.compatibility-label.incompatible{color:var(--text-warning);background:var(--surface-warning);border-color:var(--border-warning)}.lora-card .compatibility-reason{margin:10px 0}
.lora-library{margin-top:36px;border-top:1px solid var(--border-control);padding-top:24px}.lora-intro,.lora-top,.lora-actions{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}.lora-toolbar{display:flex;gap:16px;align-items:end;margin:24px 0}.lora-toolbar label:first-child{flex:1}.lora-toolbar label,.lora-form label{display:grid;gap:8px;font-size:12px}.lora-toolbar .muted{padding-bottom:12px;white-space:nowrap}.lora-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.lora-card{margin:0;min-width:0}.lora-card h3{overflow-wrap:anywhere;font-size:19px;line-height:1.6;margin-top:20px}.lora-form{display:grid;gap:14px}.lora-form input,.lora-form select,.lora-form textarea{width:100%;min-width:0;box-sizing:border-box;padding:12px}.lora-form textarea{resize:vertical}.lora-notes{white-space:pre-wrap;overflow-wrap:anywhere}.lora-card a,.lora-card summary{color:var(--text-notice);font-size:12px}.lora-card details{margin:20px 0}.lora-card summary{cursor:pointer}.lora-card dl{display:grid;gap:8px;font-size:12px;line-height:1.7}.lora-card dt{color:var(--text-muted)}.lora-card dd{margin:0;overflow-wrap:anywhere}.lora-toolbar select{padding:12px}@media(max-width:1000px){.lora-grid{grid-template-columns:1fr}}@media(max-width:700px){.lora-toolbar{flex-wrap:wrap}.lora-toolbar label:first-child{flex-basis:100%}}
</style>
