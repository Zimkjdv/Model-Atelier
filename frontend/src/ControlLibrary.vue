<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { architectures, architectureLabel, fileHash, fileSize, metadataTime, parseFileSize, safeMetadataUrl, validArchitecture } from './modelMetadata'
import type { Architecture, ModelMetadata } from './modelMetadata'

type ControlModel = ModelMetadata & { name: string; listed: boolean; version: string; notes: string; source_url: string; kind: string }
type Catalog = { engine_url: string; controlnets: ControlModel[]; synced_at: string | null; sync_error: string | null }
const props=defineProps<{engineUrl:string}>()
const catalog = ref<Catalog | null>(null), busy = ref(false), error = ref(''), feedback = ref('')
const search = ref(''), filter = ref('all'), editing = ref<string | null>(null)
const version = ref(''), architecture = ref<Architecture>('unknown'), source = ref(''), notes = ref('')
const sizeBytes = ref(''), sha256 = ref(''), licenseName = ref(''), licenseUrl = ref('')
let revision = 0
const kind=ref('unknown')
const visible = computed(() => (catalog.value?.controlnets ?? []).filter(item =>
  item.name.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()) &&
  (filter.value === 'all' || (filter.value === 'listed' ? item.listed : !item.listed))))
async function request(path = '', method = 'GET', body?: unknown): Promise<Catalog> {
  const response = await fetch('/api/controlnets' + path, { method,
    ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'ControlNet 資料無效，請檢查網址、SHA256 及欄位長度。')
  if (data.engine_url !== props.engineUrl || !Array.isArray(data.controlnets))
    throw new Error('引擎設定已變更，請重新載入模型庫；目前輸入仍保留。')
  return data
}
async function load(sync = false) {
  if (busy.value) return
  const ticket = revision, engineUrl = props.engineUrl
  busy.value = true; error.value = ''; feedback.value = ''
  try {
    const next = await request(sync ? '/sync' : '', sync ? 'POST' : 'GET', sync ? { engine_url: engineUrl } : undefined)
    if (ticket !== revision) return
    catalog.value = next
    if (sync && !next.sync_error) feedback.value = 'ControlNet 清單已同步；尚未載入或驗證權重。'
  } catch (e) { if (ticket === revision) error.value = e instanceof Error ? e.message : 'ControlNet 模型庫讀取失敗。' }
  finally { if (ticket === revision) busy.value = false }
}
function edit(item: ControlModel) {
  editing.value = item.name; version.value = item.version; architecture.value = validArchitecture(item.architecture);kind.value=item.kind
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
      kind:kind.value, version: version.value, architecture: architecture.value, source_url: source.value, notes: notes.value,
      size_bytes: parseFileSize(sizeBytes.value), sha256: hash, license_name: licenseName.value, license_url: licenseUrl.value })
    if (ticket !== revision) return
    catalog.value = next; editing.value = null; feedback.value = 'ControlNet 登記資料已保存。'
  } catch (e) { if (ticket === revision) error.value = e instanceof Error ? e.message : '保存失敗，輸入仍保留。' }
  finally { if (ticket === revision) busy.value = false }
}
watch(() => props.engineUrl, () => {
  revision++; catalog.value = null; editing.value = null; busy.value = false; error.value = ''; feedback.value = ''
  void load()
}, { immediate: true })
onBeforeUnmount(()=>{revision++;busy.value=false})
</script>

<template>
  <section class="control-library" aria-labelledby="control-heading">
    <div class="panel control-intro">
      <div><span class="chip">CONTROLNET LIBRARY</span><h2 id="control-heading">ControlNet 模型庫</h2><p>整理引擎登記的 ControlNet 及基礎架構，保存版本與來源。</p></div>
      <button type="button" class="primary" :disabled="busy || editing !== null" @click="load(true)">{{ busy ? '處理中…' : '同步 ControlNet 清單' }}</button>
    </div>
    <p class="footnote">{{ engineUrl }} · {{ catalog?.synced_at ? '最後成功同步：' + metadataTime(catalog.synced_at) : '尚未成功同步' }}</p>
    <p class="footnote">清單及資料為登記快照，未核對實際檔案。結構工作台目前接受一個 canny 控制模型，需與 checkpoint 登記相同的 SD 1.x／SDXL 架構；不依檔名推測。</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }} <button class="secondary" :disabled="busy || editing !== null" @click="load()">重新讀取 ControlNet</button></p>
    <p v-if="catalog?.sync_error" class="notice warning" role="alert">{{ catalog.sync_error }} 此處保留歷史清單，不代表目前可用。</p>
    <p v-if="feedback" class="notice success" role="status">{{ feedback }}</p>
    <div class="control-toolbar">
      <label>搜尋 ControlNet<input v-model="search" type="search" placeholder="輸入 ControlNet 名稱"></label>
      <label>ControlNet 清單狀態<select v-model="filter"><option value="all">全部紀錄</option><option value="listed">最近清單內</option><option value="missing">最近清單未列出</option></select></label>
      <span class="muted" role="status">{{ visible.length }} 個 ControlNet</span>
    </div>
    <article v-if="!catalog && busy" class="panel" role="status">正在讀取 ControlNet…</article>
    <article v-else-if="catalog && !catalog.controlnets.length" class="panel"><h3>尚無 ControlNet 登記</h3><p>將已有的 ControlNet 放入 ComfyUI 的 controlnet 目錄或其額外路徑，啟動引擎後同步。平台不會自動下載模型。</p></article>
    <p v-else-if="catalog && !visible.length" class="notice">沒有符合篩選的 ControlNet。<button class="secondary" @click="search = ''; filter = 'all'">清除 ControlNet 篩選</button></p>
    <div class="control-grid">
      <article v-for="item in visible" :key="item.name" class="panel control-card">
        <div class="control-top"><span class="chip">CONTROLNET</span><span class="status" :class="{ connected: item.listed }">{{ item.listed ? '最近清單內' : '最近清單未列出' }}</span></div>
        <h3>{{ item.name }}</h3><p>版本：{{ item.version.trim() || '未知' }}</p><p class="footnote">控制類型：{{item.kind}} · 登記基礎架構：{{ architectureLabel(item.architecture) }}</p>
        <form v-if="editing === item.name" class="control-form" @submit.prevent="save">
          <label>控制類型<select v-model="kind"><option value="unknown">未知</option><option value="canny">Canny</option><option value="depth">Depth（尚未接入）</option><option value="pose">Pose（尚未接入）</option><option value="other">其他</option></select></label>
          <label>ControlNet 版本<input v-model="version" maxlength="100" placeholder="留空表示未知"></label>
          <label>ControlNet 基礎架構（使用者登記）<select v-model="architecture"><option v-for="option in architectures" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
          <label>ControlNet 來源網址<input v-model="source" type="url" maxlength="2048" placeholder="https://…"></label>
          <label>ControlNet 檔案大小（bytes）<input v-model="sizeBytes" inputmode="numeric" maxlength="16" placeholder="留空表示未知"></label>
          <label>ControlNet SHA256<input v-model="sha256" aria-describedby="control-hash-help" maxlength="64" autocomplete="off" spellcheck="false"></label>
          <p id="control-hash-help" class="footnote">完整 64 位十六進位雜湊；登記不代表平台已驗證實際檔案。</p>
          <label>ControlNet 授權名稱<input v-model="licenseName" maxlength="200"></label>
          <label>ControlNet 授權網址<input v-model="licenseUrl" type="url" maxlength="2048" placeholder="https://…"></label>
          <label>ControlNet 備註<textarea v-model="notes" rows="3" maxlength="4000"></textarea></label>
          <div class="control-actions"><button class="primary" :disabled="busy">保存 ControlNet 資料</button><button type="button" class="secondary" :disabled="busy" @click="editing = null">取消 ControlNet 編輯</button></div>
        </form>
        <template v-else>
          <p class="control-notes">{{ item.notes || '尚未加入備註。' }}</p>
          <a v-if="safeMetadataUrl(item.source_url)" :href="safeMetadataUrl(item.source_url)" target="_blank" rel="noopener noreferrer">查看 ControlNet 登記來源 ↗</a><p v-else class="footnote">來源：未知</p>
          <details><summary>ControlNet 檔案與授權資料</summary><dl>
            <dt>大小</dt><dd>{{ fileSize(item.size_bytes) }}</dd><dt>SHA256</dt><dd>{{ fileHash(item.sha256) }}</dd>
            <dt>授權名稱</dt><dd>{{ item.license_name?.trim() || '未知' }}</dd><dt>授權條款</dt><dd><a v-if="safeMetadataUrl(item.license_url)" :href="safeMetadataUrl(item.license_url)" target="_blank" rel="noopener noreferrer">查看 ControlNet 登記條款 ↗</a><span v-else>未知</span></dd>
            <dt>登記更新時間</dt><dd>{{ metadataTime(item.metadata_updated_at) }}</dd>
          </dl></details>
          <button type="button" class="secondary" :disabled="busy || editing !== null" @click="edit(item)">編輯 ControlNet 資料</button>
        </template>
      </article>
    </div>
  </section>
</template>

<style scoped>
.control-library{margin-top:36px;border-top:1px solid var(--border-control);padding-top:24px}.control-intro,.control-top,.control-actions{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}.control-toolbar{display:flex;gap:16px;align-items:end;margin:24px 0}.control-toolbar label:first-child{flex:1}.control-toolbar label,.control-form label{display:grid;gap:8px;font-size:12px}.control-toolbar .muted{padding-bottom:12px;white-space:nowrap}.control-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.control-card{margin:0;min-width:0}.control-card h3{overflow-wrap:anywhere;font-size:19px;line-height:1.6;margin-top:20px}.control-form{display:grid;gap:14px}.control-form input,.control-form select,.control-form textarea{width:100%;min-width:0;box-sizing:border-box;padding:12px}.control-form textarea{resize:vertical}.control-notes{white-space:pre-wrap;overflow-wrap:anywhere}.control-card a,.control-card summary{color:var(--text-notice);font-size:12px}.control-card details{margin:20px 0}.control-card summary{cursor:pointer}.control-card dl{display:grid;gap:8px;font-size:12px;line-height:1.7}.control-card dt{color:var(--text-muted)}.control-card dd{margin:0;overflow-wrap:anywhere}.control-toolbar select{padding:12px}@media(max-width:1000px){.control-grid{grid-template-columns:1fr}}@media(max-width:700px){.control-toolbar{flex-wrap:wrap}.control-toolbar label:first-child{flex-basis:100%}}
</style>
