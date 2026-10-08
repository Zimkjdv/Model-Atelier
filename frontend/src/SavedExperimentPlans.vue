<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import type { ComparisonPlan, ExperimentSummary, SavedExperiment } from './experimentSettings'
const props = defineProps<{ plan:ComparisonPlan|null; disabled?:boolean }>()
const emit = defineEmits<{ open:[value:ComparisonPlan]; busy:[value:boolean] }>()
const records = ref<ExperimentSummary[]>([]), showArchived = ref(false), busy = ref(false)
const input = ref(''), imported = ref<ComparisonPlan|null>(null), error = ref(''), message = ref('')
const blocked = computed(() => props.disabled || busy.value)
const visible = computed(() => records.value.filter(item => showArchived.value || !item.archived))
let ticket = 0, controller:AbortController|null = null
const saveIds = new Map<string,string>()
function stop() { ++ticket; controller?.abort(); controller = null; busy.value = false; emit('busy',false) }
watch(input, () => { stop(); imported.value = null })
onDeactivated(stop); onBeforeUnmount(stop)
async function request(path:string, signal:AbortSignal, method='GET', body?:string) {
  const response = await fetch('/api/experiments/' + path,{ method,signal,headers:{'Content-Type':'application/json'},...(body === undefined ? {} : {body}) })
  const text = await response.text()
  if (!response.ok) {
    let detail = '操作失敗，請重新整理清單；預覽與輸入保留。'
    try { const value = JSON.parse(text); if(typeof value.detail === 'string') detail = value.detail } catch { /* Non-JSON failures stay readable. */ }
    throw new Error(detail)
  }
  return JSON.parse(text)
}
async function run(action:(signal:AbortSignal,current:number)=>Promise<void>) {
  if(blocked.value) return
  stop(); const current = ticket, abort = new AbortController(); controller = abort
  busy.value = true; emit('busy',true); error.value = ''; message.value = ''
  try { await action(abort.signal,current) }
  catch(e) { if(ticket === current && !abort.signal.aborted) error.value = e instanceof Error ? e.message : '結果未確認；請先重新整理清單，未自動重送。' }
  finally { if(ticket === current) { busy.value = false; controller = null; emit('busy',false) } }
}
async function refresh() {
  await run(async(signal,current) => {
    const result:ExperimentSummary[] = await request('plans',signal)
    if(ticket === current) { records.value = result; message.value = '已重新讀取保存方案；創作表單與未保存預覽保留。' }
  })
}
onMounted(() => { void refresh() }); onActivated(() => { if(!busy.value) void refresh() })
async function save() {
  const plan = props.plan
  if(!plan) return
  if(!saveIds.has(plan.plan_sha256)) {
    const key = 'model-atelier-experiment-save-' + plan.plan_sha256
    let previous:string|null = null
    try { previous = sessionStorage.getItem(key) } catch { /* Keep an in-memory ID when storage is unavailable. */ }
    const existing = records.value.find(item => item.plan_sha256 === plan.plan_sha256)
    const identifier = existing?.id ?? (previous && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(previous) ? previous : crypto.randomUUID())
    saveIds.set(plan.plan_sha256,identifier)
    try { sessionStorage.setItem(key,identifier) } catch { /* Never make persistence a condition for local editing. */ }
  }
  const identifier = saveIds.get(plan.plan_sha256)!
  await run(async(signal,current) => {
    const value:SavedExperiment = await request('plans',signal,'POST',JSON.stringify({request_id:identifier,plan}))
    const list:ExperimentSummary[] = await request('plans',signal)
    if(ticket === current) { records.value = list; message.value = `已保存「${value.plan.title}」。${value.archived ? '原封存狀態保留，可在清單還原。' : ''}沒有保存草稿或生成。` }
  })
}
async function open(item:ExperimentSummary) {
  await run(async(signal,current) => {
    const value:SavedExperiment = await request('plans/'+item.id,signal)
    if(ticket === current) { emit('open',value.plan); message.value = '已重載原方案預覽，創作表單保持原值。' }
  })
}
async function archive(item:ExperimentSummary) {
  await run(async(signal,current) => {
    await request('plans/'+item.id,signal,'PUT',JSON.stringify({revision:item.revision,archived:!item.archived}))
    const list:ExperimentSummary[] = await request('plans',signal)
    if(ticket === current) { records.value = list; message.value = item.archived ? '方案已還原。' : '方案已封存，完整設定及素材引用保留。' }
  })
}
async function readFile(event:Event) {
  const control = event.target as HTMLInputElement, file = control.files?.[0]
  if(!file || blocked.value) return
  stop(); imported.value = null; error.value = ''; const current = ticket
  try {
    if(file.size > 1024*1024) throw new Error('比較方案不可超過 1 MiB。')
    const text = await file.text()
    if(ticket === current) { input.value = text; message.value = `已讀取 ${file.name}，請驗證並預覽。` }
  } catch(e) { if(ticket === current) error.value = e instanceof Error ? e.message : '檔案無法讀取。' }
  finally { control.value = '' }
}
async function validate() {
  await run(async(signal,current) => {
    if(new Blob([input.value]).size > 1024*1024) throw new Error('比較方案不可超過 1 MiB。')
    const value:ComparisonPlan = await request('import-preview',signal,'POST',input.value)
    if(ticket === current) { imported.value = value; message.value = '文件已驗證，請檢查完整方案後明確使用；尚未保存或載入創作設定。' }
  })
}
function adopt() {
  if(blocked.value || !imported.value) return
  emit('open',imported.value); imported.value = null; message.value = '已使用匯入方案的預覽；需要另按保存，或逐組載入與生成。'
}
</script>
<template>
  <details class="saved-experiments"><summary>保存方案與 JSON 匯入</summary>
    <p class="footnote">保存完整方案供下次繼續。原方案不可覆寫，修改後請保存新方案；封存可還原。保存不生成，也不保存創作草稿。</p>
    <button type="button" class="secondary" :disabled="blocked || !plan" @click="save">保存目前預覽方案</button>
    <p class="footnote">保存結果未確認時，先重新整理清單；平台不自動重送，相同方案優先沿用本視窗的請求或已有紀錄。</p>
    <button type="button" class="secondary" :disabled="blocked" @click="refresh">重新整理已保存方案</button>
    <label class="archive-toggle"><input v-model="showArchived" type="checkbox" :disabled="blocked">顯示封存方案</label>
    <p v-if="!visible.length" class="footnote">目前沒有符合條件的保存方案。</p>
    <article v-for="item in visible" :key="item.id" class="saved-plan"><strong>{{ item.title }}{{ item.archived ? '（封存）' : '' }}</strong><p>{{ item.workflow_id }} · {{ item.axis }} · {{ item.expected_job_count }} 組 · 修訂 {{ item.revision }}</p><p class="footnote">{{ item.plan_sha256 }}</p><button type="button" class="secondary" :disabled="blocked" :aria-label="'重載比較方案 ' + item.title" @click="open(item)">重載方案預覽</button><button type="button" class="secondary" :disabled="blocked" :aria-label="(item.archived ? '還原' : '封存') + '比較方案 ' + item.title" @click="archive(item)">{{ item.archived ? '還原' : '封存' }}</button></article>
    <label for="experiment-import-file">讀取比較方案 JSON（最多 1 MiB）</label><input id="experiment-import-file" type="file" accept=".json,application/json" :disabled="blocked" @change="readFile">
    <label for="experiment-import-json">或貼上比較方案 JSON</label><textarea id="experiment-import-json" v-model="input" rows="4" :disabled="blocked" spellcheck="false" aria-describedby="experiment-import-help"/>
    <p id="experiment-import-help" class="footnote">文件只包含設定，不包含模型權重或素材圖片。驗證不改創作表單；使用後逐組明確載入設定。</p>
    <button type="button" class="secondary" :disabled="blocked || !input.trim()" @click="validate">驗證並預覽比較文件</button>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p><p v-if="message" class="notice" role="status">{{ message }}</p>
    <section v-if="imported" aria-label="匯入比較方案確認"><h3>{{ imported.title }} · {{ imported.expected_job_count }} 組</h3><ul><li v-for="warning in imported.warnings" :key="warning">{{ warning }}</li></ul><details><summary>完整比較文件</summary><pre>{{ JSON.stringify(imported,null,2) }}</pre></details><p class="footnote">使用會取代下方的方案預覽，創作表單保持原值。</p><button type="button" class="secondary" :disabled="blocked" @click="adopt">使用此方案預覽</button><button type="button" class="secondary" :disabled="blocked" @click="imported = null">取消匯入</button></section>
  </details>
</template>
<style scoped>
.saved-experiments{margin:18px 0;padding:14px;border:1px solid var(--border-control);border-radius:8px;min-width:0;overflow-wrap:anywhere}.saved-plan{margin:14px 0;padding:12px;background:var(--surface-input);border-radius:7px}label{display:block;margin:16px 0 8px}input,textarea{box-sizing:border-box;width:100%;font:inherit}textarea{padding:10px;background:var(--surface-input);color:var(--text-primary);border:1px solid var(--border-control);border-radius:7px;resize:vertical}.archive-toggle{display:flex;align-items:center;gap:8px}.archive-toggle input{width:auto}button{margin:8px 8px 8px 0}pre{max-height:280px;overflow:auto;white-space:pre-wrap}ul{padding-left:20px;line-height:1.8}
</style>
