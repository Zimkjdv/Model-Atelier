<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { fluxRoles, type FluxCatalog, type FluxComponent } from './fluxSettings'
import { fileSize, safeMetadataUrl, parseFileSize, architectures } from './modelMetadata'
const catalog = ref<FluxCatalog | null>(null), busy = ref(false), error = ref(''), search = ref('')
const editing = ref<{ category: string; name: string; version: string; source_url: string; architecture: string; sha256: string; size: string; license_name: string; license_url: string; notes: string } | null>(null)
const groups = [{ key:'diffusion_models', label:'主模型' }, { key:'text_encoders', label:'文字編碼器（CLIP-L／T5）' }, { key:'vae', label:'VAE' }]
let ticket = 0, abort: AbortController | null = null
async function api(path: string, options?: RequestInit) {
  const response = await fetch('/api/' + path, options), value = await response.json()
  if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : '請檢查元件資料或引擎設定。')
  return value
}
const entries = computed(() => groups.map(group => ({...group, items: (catalog.value?.groups[group.key] || []).filter(item => (item.name + item.version + item.notes).toLowerCase().includes(search.value.toLowerCase())) })))
async function load(sync = false) {
  const token = ++ticket; abort?.abort(); const controller = new AbortController(); abort = controller
  busy.value = true; error.value = ''
  try {
    const settings = await api('settings', {signal:controller.signal})
    const inventory = await api('flux/components' + (sync ? '/sync' : ''), sync ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({engine_url:settings.comfy_url}),signal:controller.signal} : {signal:controller.signal})
    const latest = await api('settings',{signal:controller.signal})
    if (token !== ticket) return
    if (inventory.engine_url !== latest.comfy_url || settings.comfy_url !== latest.comfy_url) throw new Error('引擎已變更，請重新讀取元件庫。')
    catalog.value = inventory; error.value = inventory.sync_error || ''
  } catch (e) { if (token === ticket && !(e instanceof DOMException && e.name === 'AbortError')) error.value = e instanceof Error ? e.message : '讀取失敗' }
  finally { if (token === ticket) busy.value = false }
}
function edit(category: string, item: FluxComponent) {
  editing.value = { category, name:item.name, version:item.version || '', source_url:item.source_url || '', architecture:item.architecture || 'unknown', sha256:item.sha256 || '', size:item.size_bytes == null ? '' : String(item.size_bytes), license_name:item.license_name || '', license_url:item.license_url || '', notes:item.notes || '' }
}
async function save() {
  if (!editing.value || !catalog.value || busy.value) return
  busy.value = true; error.value = ''
  try {
    const {size,...value} = editing.value
    const size_bytes = parseFileSize(size)
    catalog.value = await api('flux/components/metadata',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...value,engine_url:catalog.value.engine_url,size_bytes})})
    editing.value = null
  } catch (e) {error.value = e instanceof Error ? e.message : '保存失敗'}
  finally {busy.value = false}
}
onMounted(() => void load()); onBeforeUnmount(() => {++ticket;abort?.abort()})
</script>
<template>
  <section class="panel component-library" aria-label="FLUX 元件庫"><div class="component-heading"><h2>FLUX 分離元件庫</h2><button class="secondary" :disabled="busy || !!editing" @click="load(true)">{{busy ? '處理中…' : '同步 FLUX 模型清單'}}</button></div>
    <p class="footnote">來源：{{catalog?.engine_url || '讀取中'}} · {{catalog?.synced_at ? new Date(catalog.synced_at).toLocaleString() : '尚未同步'}}。此清單與下方固定下載計畫分開；名稱不代表 FLUX 變體或相容性已驗證。</p>
    <p v-if="error" class="notice warning" role="alert">{{error}}</p><label for="flux-component-search">搜尋 FLUX 元件</label><input id="flux-component-search" v-model="search" type="search">
    <form v-if="editing" class="component-edit" @submit.prevent="save"><fieldset :disabled="busy"><h3>{{editing.name}}</h3><label>元件版本<input v-model="editing.version" maxlength="100" placeholder="未登記即未知"></label><label>元件來源網址<input v-model="editing.source_url" maxlength="2048" type="url"></label><label>登記架構<select v-model="editing.architecture"><option v-for="item in architectures" :key="item.value" :value="item.value">{{item.label}}</option></select></label><label>完整 SHA256<input v-model="editing.sha256" maxlength="64" pattern="[a-fA-F0-9]{64}|"></label><label>檔案大小 bytes<input v-model="editing.size" inputmode="numeric"></label><label>授權名稱<input v-model="editing.license_name" maxlength="200"></label><label>授權網址<input v-model="editing.license_url" maxlength="2048" type="url"></label><label>元件備註<textarea v-model="editing.notes" maxlength="4000" rows="3" /></label><div class="component-actions"><button class="primary" type="submit">保存元件資料</button><button class="secondary" type="button" @click="editing = null">取消元件編輯</button></div></fieldset></form>
    <template v-for="group in entries" :key="group.key"><h3>{{group.label}}</h3><p v-if="!group.items.length" class="footnote">目前沒有符合的元件；請安裝後同步。</p><article v-for="item in group.items" :key="item.name" class="component-row"><strong>{{item.name}}</strong><p>版本 {{item.version || '未知'}} · {{item.listed ? '上次清單已列出' : '最近同步未列出'}} · {{fileSize(item.size_bytes)}}</p><p v-if="safeMetadataUrl(item.source_url)"><a :href="safeMetadataUrl(item.source_url)!" target="_blank" rel="noopener">登記來源 ↗</a></p><p v-if="item.notes">{{item.notes}}</p><button class="secondary" :disabled="busy || !!editing" :aria-label="'編輯 FLUX 元件：' + item.name" @click="edit(group.key,item)">登記版本與來源</button></article></template>
    <p class="footnote">四個生成角色：{{fluxRoles.map(role => role.label).join('、')}}。版本、來源、大小及雜湊均為登記資料；沒有版本就顯示未知。</p>
  </section>
</template>
<style scoped>
.component-library{margin-top:28px;min-width:0;overflow-wrap:anywhere;font-size:12px}.component-heading,.component-actions{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}.component-library h2{font-size:20px}.component-library h3{font-size:14px;margin:24px 0 12px}.component-library label{display:block;margin:14px 0}.component-library input,.component-library select,.component-library textarea{width:100%;box-sizing:border-box;margin-top:9px;font:inherit}.component-library select,.component-library textarea{background:var(--surface-input);color:var(--text-primary);border:1px solid var(--border-control);border-radius:7px;padding:12px}.component-library a{color:var(--focus-ring)}.component-row{border-top:1px solid var(--border-control);padding:18px 0}.component-edit{padding:16px;background:var(--surface-input);border:1px solid var(--border-control);border-radius:8px;margin-top:20px}.component-edit fieldset{border:0;margin:0;padding:0;min-width:0}.component-row p{line-height:1.7;white-space:pre-wrap}
</style>
