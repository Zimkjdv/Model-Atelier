<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'
type Purpose = 'unspecified' | 'style' | 'character' | 'composition'
type Asset = { id: string; title: string; width: number; height: number; size: number; archived: boolean; purpose: Purpose; revision: number; preprocessing: { version: number; library_version: string } | null }
type Workflow = { id: string; name: string; implemented: boolean; input_requirement: string; control: string }
const purposes: Record<Purpose, string> = { unspecified: '未指定', style: '視覺風格', character: '角色外觀', composition: '構圖' }
const purpose = ref<Purpose>('unspecified'), filter = ref(''), workflows = ref<Workflow[]>([])
const items = ref<Asset[]>([]), busy = ref(false), error = ref(''), message = ref(''), archived = ref(false), search = ref('')
const editing = ref<string | null>(null), title = ref('')
const visible = computed(() => items.value)
const total = ref(0), next = ref<string | null>(null), previous = ref<string | null>(null)
const reads = createRequestScope()
let timer: ReturnType<typeof setTimeout>
function api<T>(path = '', options?: RequestInit): Promise<T> { return apiJson<T>('assets' + path, options) }
async function load(cursor: string | null = null) {
  if (editing.value) return
  const read = reads.begin()
  busy.value = true; error.value = ''
  try {
    const query = new URLSearchParams({ limit: '40', q: search.value, scope: archived.value ? 'archived' : 'active', purpose: filter.value })
    if (cursor) query.set('cursor', cursor)
    const [page, definitions] = await Promise.all([
      apiJson<{ items: Asset[]; total: number; next_cursor: string | null; previous_cursor: string | null }>('library/assets?' + query, { signal: read.signal }),
      apiJson<Workflow[]>('reference-workflows', { signal: read.signal }),
    ])
    if (!read.isCurrent()) return
    workflows.value = definitions; items.value = page.items; total.value = page.total
    next.value = page.next_cursor; previous.value = page.previous_cursor
  } catch (e) { if (read.isCurrent()) error.value = e instanceof Error ? e.message : '無法讀取素材' }
  finally { if (read.isCurrent()) busy.value = false }
}
watch([search, archived, filter], () => { clearTimeout(timer); reads.cancel(); busy.value = true; timer = setTimeout(() => void load(), 250) })
onBeforeUnmount(() => { clearTimeout(timer); reads.dispose() })
async function upload(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  if (!file) return
  busy.value = true; error.value = ''; message.value = ''
  try {
    if (file.size > 20 * 1024 * 1024) throw new Error('圖片不可超過 20 MiB')
    const item = await api<Asset>('?filename=' + encodeURIComponent(file.name), { method: 'POST', body: file, headers: { 'Content-Type': 'application/octet-stream' } })
    archived.value = false; search.value = ''; filter.value = ''; await load(); message.value = '參考素材已保存，可以回到創作工作台選取。'
  } catch (e) { error.value = e instanceof Error ? e.message : '上傳失敗' }
  finally { busy.value = false; input.value = '' }
}
async function update(item: Asset, archive = item.archived) {
  busy.value = true; error.value = ''; message.value = ''
  try {
    const result = await api<Asset>('/' + item.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: editing.value === item.id ? title.value : item.title, purpose: editing.value === item.id ? purpose.value : item.purpose, archived: archive, revision: item.revision }) })
    items.value = items.value.map(value => value.id === result.id ? result : value)
    editing.value = null; await load(); message.value = '素材資料已更新。'
  } catch (e) { error.value = e instanceof Error ? e.message : '更新失敗' }
  finally { busy.value = false }
}
onMounted(() => void load())
</script>

<template>
  <p v-if="busy" class="footnote" role="status">正在處理素材，請稍候…</p>
  <article class="panel upload-panel"><span class="chip">REFERENCE ASSETS</span><h2>收集創作的起點</h2><p>標記參考用途，再於創作工作台選擇相容流程。用途標籤僅供整理，不會自動套用畫風或鎖定角色。</p><label class="upload-label">選擇圖片<input type="file" aria-describedby="asset-upload-help" accept="image/png,image/jpeg,image/webp" :disabled="busy" @change="upload"></label><p id="asset-upload-help" class="footnote">支援單張 PNG、JPEG、WebP，最多 20 MiB、1600 萬像素。保留原始檔於你的電腦；平台儲存經方向校正、移除中繼資料的 PNG 副本。</p></article>
  <details class="panel"><summary>參考流程的輸入需求與支援能力</summary><article v-for="workflow in workflows" :key="workflow.id"><h3>{{ workflow.name }} · {{ workflow.implemented ? '已實作，提交仍需引擎驗證' : '尚未整合' }}</h3><p>{{ workflow.input_requirement }} {{ workflow.control }}</p></article></details>
  <p v-if="error" class="notice warning" role="alert">{{ error }}</p><p v-if="message" class="notice" role="status">{{ message }}</p>
  <div class="asset-toolbar"><label>搜尋素材<input v-model="search" :disabled="editing !== null" maxlength="200" type="search" placeholder="輸入素材名稱"></label><label>參考用途<select v-model="filter" :disabled="editing !== null"><option value="">全部用途</option><option v-for="(label, value) in purposes" :key="value" :value="value">{{ label }}</option></select></label><button class="secondary" :disabled="busy || editing !== null" @click="archived = !archived">{{ archived ? '查看使用中素材' : '查看已封存' }}</button><button class="secondary" :disabled="busy || editing !== null" @click="load()">重新整理</button></div>
  <p class="footnote">{{ archived ? '已封存' : '使用中' }} · {{ total }} 張符合素材</p>
  <div class="asset-toolbar" aria-label="素材分頁"><button class="secondary" :disabled="busy || editing !== null || !previous" @click="load(previous)">上一頁</button><button class="secondary" :disabled="busy || editing !== null || !next" @click="load(next)">下一頁</button></div>
  <article v-if="!visible.length" class="panel placeholder"><h2>{{ busy ? '處理中…' : '目前沒有符合條件的素材' }}</h2><p>上傳圖片，或調整搜尋與封存篩選。</p></article>
  <p role="status" class="footnote">{{ archived ? '已封存' : '使用中' }}素材：{{ total }} 張符合，本頁 {{ visible.length }} 張</p><div class="asset-grid"><article v-for="item in visible" :key="item.id" class="panel asset-card"><a :href="'/api/assets/' + item.id + '/image'" target="_blank" rel="noopener"><img :src="'/api/assets/' + item.id + '/image'" :alt="item.title" loading="lazy"></a><template v-if="editing === item.id"><label>素材名稱<input v-model="title" maxlength="100" :disabled="busy"></label><label>素材用途<select v-model="purpose" :disabled="busy"><option v-for="(label, value) in purposes" :key="value" :value="value">{{ label }}</option></select></label><div class="asset-actions"><button class="primary" :disabled="busy || !title.trim()" @click="update(item)">保存素材資料</button><button class="secondary" :disabled="busy" @click="editing = null">取消</button></div></template><template v-else><h2>{{ item.title }}</h2><p>{{ purposes[item.purpose] }} · {{ item.width }} × {{ item.height }} · {{ (item.size / 1024 / 1024).toFixed(2) }} MiB</p><p class="footnote">{{ item.preprocessing ? '正規化 v' + item.preprocessing.version + ' · Pillow ' + item.preprocessing.library_version : '前處理版本未知' }}</p><div class="asset-actions"><button class="secondary" :disabled="busy || editing !== null" :aria-label="'編輯素材 ' + item.title" @click="editing = item.id; title = item.title; purpose = item.purpose">編輯資料</button><button class="secondary" :disabled="busy || editing !== null" @click="update(item, !item.archived)">{{ item.archived ? '還原素材' : '封存素材' }}</button></div></template></article></div>
</template>

<style scoped>
.upload-panel{background:linear-gradient(120deg,#253b2d,#191d20)}.upload-label{display:grid;gap:12px;font-size:12px;max-width:420px}.upload-label input{font-size:12px}.asset-toolbar{display:flex;align-items:end;gap:12px;flex-wrap:wrap}.asset-toolbar label{flex:1;display:grid;gap:8px;font-size:12px}.asset-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.asset-card{margin-bottom:0;min-width:0}.asset-card img{width:100%;height:200px;object-fit:contain;background:#101617;border-radius:8px}.asset-card h2{overflow-wrap:anywhere;font-size:14px;margin-top:20px}.asset-card p{font-size:11px}.asset-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:15px}.asset-card label{display:grid;gap:8px;font-size:12px;margin-top:15px}@media(max-width:1100px){.asset-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.asset-grid{grid-template-columns:1fr}.asset-toolbar label{flex-basis:100%}}
</style>
