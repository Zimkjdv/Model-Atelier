<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import GenerationPanel from './GenerationPanel.vue'
type Asset = { id: string; title: string; archived: boolean }
type Draft = { reference_ids?: string[]; id: string; title: string; prompt: string; engine_url: string; checkpoint: string; width: number; height: number; seed: string; revision: number; model_version: string; updated_at: string }
type Model = { name: string; listed: boolean; version?: string }
type Catalog = { engine_url: string; models: Model[]; selected: string | null }
const emit = defineEmits<{ models: []; assets: []; gallery: [jobId: string] }>()
const form = reactive({ title: '未命名創作', prompt: '', engine_url: '', checkpoint: '', width: 1024, height: 1024, seed: '0', reference_ids: [] as string[] })
const id = ref<string | null>(null), revision = ref<number | null>(null), records = ref<Draft[]>([]), models = ref<Catalog | null>(null)
const busy = ref(false), error = ref(''), message = ref(''), saved = ref(''), pending = ref<Draft | 'new' | null>(null)
const dirty = computed(() => JSON.stringify(form) !== saved.value)
const selected = computed(() => models.value?.engine_url === form.engine_url ? models.value.models.find(m => m.name === form.checkpoint) : undefined)
const draftVersion = ref('')
const references = ref<Asset[]>([])
const modelVersion = computed(() => selected.value?.version || draftVersion.value || '未知')
const available = computed(() => models.value?.engine_url === form.engine_url ? models.value.models.filter(m => m.listed) : [])
const aspect = computed(() => Number(form.width) > 0 && Number(form.height) > 0 ? `${form.width} / ${form.height}` : '1 / 1')
async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api/' + path, { method, ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : '請檢查名稱、尺寸與 seed：尺寸需為 64–8192 的 8 倍數，seed 為有效的非負整數。')
  }
  return response.json()
}
function apply(record: Draft | 'new') {
  if (record === 'new') {
    Object.assign(form, { title: '未命名創作', prompt: '', engine_url: models.value?.engine_url ?? '', checkpoint: models.value?.models.find(m => m.listed && m.name === models.value?.selected)?.name ?? '', width: 1024, height: 1024, seed: '0', reference_ids: [] as string[] })
    id.value = null; revision.value = null; draftVersion.value = ''
  } else {
    Object.assign(form, { title: record.title, prompt: record.prompt, engine_url: record.engine_url, checkpoint: record.checkpoint, width: record.width, height: record.height, seed: record.seed, reference_ids: record.reference_ids ?? [] })
    id.value = record.id; revision.value = record.revision; draftVersion.value = record.model_version
  }
  saved.value = JSON.stringify(form); pending.value = null; error.value = ''; message.value = ''
}
function choose(record: Draft | 'new') { if (dirty.value) pending.value = record; else apply(record) }
async function refresh() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    const [list, catalog, assets] = await Promise.all([api<Draft[]>('drafts'), api<Catalog>('models'), api<Asset[]>('assets')])
    records.value = list; models.value = catalog; references.value = assets
    if (!form.engine_url && !dirty.value) apply('new')
  } catch (e) { error.value = e instanceof Error ? e.message : '無法讀取草稿' }
  finally { busy.value = false }
}
async function save(copy = false) {
  if (busy.value) return
  busy.value = true; error.value = ''; message.value = ''
  try {
    const record = await api<Draft>(id.value && !copy ? 'drafts/' + id.value : 'drafts', id.value && !copy ? 'PUT' : 'POST', { ...form, revision: revision.value })
    apply(record)
    records.value = [record, ...records.value.filter(r => r.id !== record.id)]
    message.value = '草稿已保存到本機。尚未提交生成任務。'
  } catch (e) { error.value = e instanceof Error ? e.message : '保存失敗' }
  finally { busy.value = false }
}
function randomSeed() {
  const bytes = crypto.getRandomValues(new Uint32Array(2))
  form.seed = ((BigInt(bytes[0]!) << 32n) | BigInt(bytes[1]!)).toString()
}
function beforeUnload(event: BeforeUnloadEvent) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
onMounted(() => { saved.value = JSON.stringify(form); void refresh(); window.addEventListener('beforeunload', beforeUnload) })
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
onActivated(() => { if (form.engine_url) void refresh() })
</script>

<template>
  <div class="studio">
    <div class="studio-toolbar"><span class="chip">創作草稿</span><span class="muted">{{ dirty ? '尚有未保存變更' : id ? '已保存 · 修訂 ' + revision : '新草稿' }}</span><button class="secondary" :disabled="busy" @click="choose('new')">＋ 新草稿</button><button class="secondary" :disabled="busy" @click="refresh">重新整理清單</button></div>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p><p v-if="message" class="notice" role="status">{{ message }}</p>
    <div v-if="pending" class="notice warning" role="alert"><p>載入其他草稿會取代目前未保存的內容。</p><button class="secondary" @click="pending = null">繼續編輯</button> <button class="secondary" @click="apply(pending)">捨棄變更並載入</button></div>
    <div class="studio-grid">
      <form class="panel editor" @submit.prevent="save()"><fieldset :disabled="busy">
        <label for="draft-title">草稿名稱</label><input id="draft-title" v-model="form.title" required maxlength="100">
        <label for="draft-model">Checkpoint 模型</label><select id="draft-model" v-model="form.checkpoint" @change="draftVersion = ''"><option value="">尚未選擇模型</option><option v-if="form.checkpoint && !available.some(m => m.name === form.checkpoint)" :value="form.checkpoint">{{ form.checkpoint }}（目前清單未列出）</option><option v-for="model in available" :key="model.name" :value="model.name">{{ model.name }}</option></select>
        <p class="footnote">模型版本：{{ modelVersion }} · {{ form.engine_url || '等待讀取引擎設定' }}</p>
        <p v-if="!available.length" class="inline-note">目前沒有可選的 checkpoint。仍可先保存創作草稿。 <button type="button" class="text-button" @click="emit('models')">前往模型庫 →</button></p>
        <p v-else-if="form.checkpoint && !selected?.listed" class="inline-note">這份草稿的模型未在目前清單中，保留原設定供整理。</p>
        <label for="draft-prompt">畫面描述 <small>{{ form.prompt.length }} / 20000</small></label><textarea id="draft-prompt" v-model="form.prompt" maxlength="20000" rows="7" placeholder="描述角色、場景、光線與你想呈現的畫面…"></textarea>
        <div class="size-presets"><button v-for="preset in [{label:'正方形',w:1024,h:1024},{label:'直式',w:832,h:1216},{label:'橫式',w:1216,h:832}]" :key="preset.label" type="button" class="secondary" @click="form.width=preset.w;form.height=preset.h">{{ preset.label }}</button></div>
        <div class="size-fields"><label for="width">寬度<input id="width" v-model.number="form.width" type="number" min="64" max="8192" step="8" required></label><label for="height">高度<input id="height" v-model.number="form.height" type="number" min="64" max="8192" step="8" required></label></div>
        <details><summary>參考素材（{{ form.reference_ids.length }} / 8）</summary><p class="footnote">此階段僅保存素材關聯，尚未套用至生成流程。</p><button class="secondary" type="button" @click="emit('assets')">管理／上傳參考圖 →</button><div class="reference-list"><label v-for="asset in references.filter(a => !a.archived || form.reference_ids.includes(a.id))" :key="asset.id"><input v-model="form.reference_ids" type="checkbox" :value="asset.id" :disabled="!form.reference_ids.includes(asset.id) && form.reference_ids.length >= 8"><img :src="'/api/assets/' + asset.id + '/image'" :alt="asset.title">{{ asset.title }}{{ asset.archived ? '（已封存）' : '' }}</label></div><p v-if="!references.length" class="footnote">尚無素材，可先到參考素材頁上傳圖片。</p></details>
        <details><summary>進階設定</summary><label for="seed">Seed</label><div class="seed-field"><input id="seed" v-model="form.seed" inputmode="numeric" pattern="[0-9]{1,20}" required><button type="button" class="secondary" @click="randomSeed">隨機</button></div><p class="footnote">以文字精確保存 64 位元整數，避免瀏覽器數字精度造成變更。</p></details>
        <div class="save-actions"><button class="primary" :disabled="!form.engine_url">{{ busy ? '處理中…' : '保存草稿' }}</button><button v-if="id" type="button" class="secondary" @click="save(true)">另存新草稿</button></div>
      </fieldset></form>
      <div><GenerationPanel :form="form" @gallery="emit('gallery', $event)"/><article class="panel canvas-panel"><div class="panel-heading"><h2>畫布比例預覽</h2><span class="badge">{{ form.width }} × {{ form.height }}</span></div><div class="canvas-area"><div class="canvas" :style="{aspectRatio:aspect,width:`min(100%, ${Math.min(300, 320 * Number(form.width) / Number(form.height))}px)`}"><span>◈</span><p>為下一張作品留下構想</p><small>此處僅預覽比例，不是生成結果</small></div></div><p>使用「生成圖片」提交目前表單。保存草稿不會啟動 GPU 任務。</p></article>
      <article class="panel"><h2>已保存草稿 <span class="muted">{{ records.length }}</span></h2><p v-if="!records.length" class="muted">保存第一份草稿後，可以在這裡接續編輯。</p><button v-for="record in records" :key="record.id" class="draft-row" :class="{chosen:id===record.id}" :disabled="busy" @click="choose(record)"><strong>{{ record.title }}</strong><span>{{ record.width }} × {{ record.height }} · {{ new Date(record.updated_at).toLocaleString() }}</span><small>{{ record.checkpoint || '未選擇模型' }} · 版本 {{ record.model_version || '未知' }}</small></button></article></div>
    </div>
  </div>
</template>

<style scoped>
.reference-list label{display:flex;align-items:center;gap:10px;overflow-wrap:anywhere}.reference-list input{width:16px;flex-shrink:0}.reference-list img{width:48px;height:48px;object-fit:contain;flex-shrink:0}
.studio-toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:22px;font-size:12px}.studio-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:22px}.editor fieldset{border:0;padding:0;margin:0;min-width:0}.editor label{display:block;font-size:12px;margin:22px 0 10px}.editor label:first-child{margin-top:0}.editor label small{float:right;color:#8a9990}.editor select,.editor textarea{width:100%;padding:12px;background:#101517;color:#e5ebe7;border:1px solid #4c5855;border-radius:7px;font:inherit;font-size:13px}.editor textarea{resize:vertical;line-height:1.8}.editor select:focus-visible,.editor textarea:focus-visible{outline:2px solid #adceb0;outline-offset:3px}.size-fields{display:grid;grid-template-columns:1fr 1fr;gap:15px}.size-fields label{margin:14px 0}.size-fields input{margin-top:10px}.size-presets,.seed-field,.save-actions{display:flex;gap:10px;flex-wrap:wrap}.size-presets{margin-top:18px}.seed-field{flex-wrap:nowrap}.seed-field input{min-width:0}.seed-field button{flex-shrink:0}.save-actions{margin-top:24px}.inline-note{background:#202b24;border-radius:7px;padding:12px;font-size:12px}.text-button{padding:0;background:none;color:#c5dfba;font-size:12px}.editor details{border-top:1px solid #35403a;padding-top:18px;margin-top:10px}.editor summary{font-size:12px;cursor:pointer}.canvas-area{min-height:310px;display:grid;place-items:center;padding:25px 0}.canvas{width:min(100%,300px);min-height:0;background:linear-gradient(150deg,#2d3b31,#141c1a);border:1px dashed #6b8169;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:12px;overflow:hidden}.canvas>span{font-size:35px;color:#aec5a1}.canvas p{font-size:12px}.canvas small{font-size:10px;color:#8c9e93}.canvas-panel>p{font-size:11px}.draft-row{display:block;width:100%;text-align:left;background:#13191a;border:1px solid #303d37;border-radius:8px;color:#d9e5dc;margin-top:12px;padding:14px;overflow-wrap:anywhere}.draft-row.chosen{border-color:#9ebc90}.draft-row span,.draft-row small{display:block;font-size:10px;color:#94a79a;margin-top:8px}.draft-row strong{font-size:13px}@media(max-width:1100px){.studio-grid{grid-template-columns:1fr}}@media(max-width:700px){.canvas-panel .panel-heading{align-items:start;flex-direction:column}.studio-toolbar .muted{flex-basis:60%}}
</style>
