<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import type { CreationForm } from './creationSettings'
import type { ImportPreview } from './settingsTransfer'
import SavedExperimentPlans from './SavedExperimentPlans.vue'
import type { ComparisonPlan as Plan, ExperimentSuite as Suite, ExperimentVariant as Variant } from './experimentSettings'
const props = defineProps<{ settings: CreationForm; dirty: boolean; disabled?: boolean }>()
const emit = defineEmits<{ apply: [value: ImportPreview] }>()
const title = ref('插畫參數比較'), axis = ref('steps'), values = ref('[4, 8]'), caseIds = ref<string[]>([]), targetLora = ref('')
const suite = ref<Suite | null>(null), plan = ref<Plan | null>(null), error = ref(''), message = ref(''), busy = ref(false)
const previewBody = ref(''), exported = ref(''), exportedUrl = ref(''), loaded = ref<string[]>([])
let ticket = 0, controller: AbortController | null = null, suiteAbort: AbortController | null = null
const documentBusy = ref(false)
const blocked = computed(() => props.disabled || busy.value || documentBusy.value)
const isLoraAxis = computed(() => axis.value.startsWith('lora_strength_'))
const activeLoras = computed(() => props.settings.loras.filter(item => item.enabled))
function canonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']'
  if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical((value as Record<string,unknown>)[key])).join(',') + '}'
  return JSON.stringify(value) ?? 'null'
}
const changed = computed(() => plan.value && canonical(props.settings) !== canonical(plan.value.baseline))
function stop() { ++ticket; controller?.abort(); controller = null; busy.value = false }
function reset() { stop(); plan.value = null; previewBody.value = ''; loaded.value = []; message.value = '' }
watch(() => JSON.stringify([title.value, axis.value, values.value, caseIds.value, targetLora.value]), reset)
async function loadSuite() {
  suiteAbort?.abort(); const abort = new AbortController(); suiteAbort = abort
  try {
    const response = await fetch('/api/experiments/suite', { signal: abort.signal })
    if (!response.ok) throw new Error('固定測試集暫時無法讀取，請重新開啟頁面；仍可比較目前提示詞。')
    const value: Suite = await response.json()
    if (!abort.signal.aborted) suite.value = value
  } catch(e) { if (!abort.signal.aborted) error.value = e instanceof Error ? e.message : '讀取失敗。' }
}
onMounted(() => { void loadSuite() })
onActivated(() => { if (!suite.value) void loadSuite() })
onDeactivated(() => { stop(); suiteAbort?.abort() })
onBeforeUnmount(() => { stop(); suiteAbort?.abort(); if(exportedUrl.value) URL.revokeObjectURL(exportedUrl.value) })
async function request(path: string, body: string, signal: AbortSignal) {
  const response = await fetch('/api/experiments/' + path, { method:'POST', signal, headers:{ 'Content-Type':'application/json' }, body })
  const text = await response.text()
  if (!response.ok) { const value = JSON.parse(text); throw new Error(typeof value.detail === 'string' ? value.detail : '比較方案格式無效，未建立任務。') }
  return text
}
async function preview() {
  if (blocked.value) return
  reset(); error.value = ''; const current = ticket, abort = new AbortController(); controller = abort; busy.value = true
  try {
    const parsed: unknown = JSON.parse(values.value)
    if (!Array.isArray(parsed)) throw new Error('參數值需為 JSON 陣列，例如 [4, 8]；seed 用字串陣列。')
    const body = JSON.stringify({ title:title.value, settings:props.settings, axis:axis.value, values:parsed, case_ids:caseIds.value, ...(isLoraAxis.value ? { target_lora:targetLora.value } : {}) })
    const value: Plan = JSON.parse(await request('preview', body, abort.signal))
    if (current === ticket) { plan.value = value; previewBody.value = body; message.value = '已建立比較預覽，尚未保存草稿或生成。' }
  } catch(e) { if (current === ticket && !abort.signal.aborted) error.value = e instanceof Error ? e.message : '預覽失敗。' }
  finally { if (current === ticket) { busy.value = false; controller = null } }
}
function apply(variant: Variant) {
  if (blocked.value || !plan.value) return
  emit('apply',{bundle:{kind:'model-atelier-creation',schema_version:1,workflow_id:plan.value.workflow_id,settings:variant.settings,source_snapshot:null},warnings:plan.value.warnings})
  if (!loaded.value.includes(variant.id)) loaded.value.push(variant.id)
  message.value = `已載入 ${variant.id} 為新草稿；請檢查後另按生成。其他方案保留，未自動提交。`
}
function openPlan(value: Plan) {
  if (props.disabled || busy.value) return
  reset(); plan.value = JSON.parse(JSON.stringify(value)) as Plan
  error.value = ''; message.value = '已載入保存／匯入方案的完整預覽；創作表單保持原值。每組仍需明確載入並生成。'
}
async function exportPlan() {
  if (blocked.value || !plan.value) return
  stop(); const current = ticket, abort = new AbortController(); controller = abort; busy.value = true; error.value = ''
  try {
    const body = previewBody.value ? JSON.stringify({ ...JSON.parse(previewBody.value), expected_plan_sha256:plan.value.plan_sha256 }) : JSON.stringify(plan.value)
    const text = await request(previewBody.value ? 'export' : 'document-export', body, abort.signal)
    if (current !== ticket) return
    exported.value = text
    if (exportedUrl.value) URL.revokeObjectURL(exportedUrl.value)
    exportedUrl.value = URL.createObjectURL(new Blob([text],{type:'application/json'}))
    message.value = '比較方案 JSON 已準備，請使用下方連結下載；未生成任何任務。'
  } catch(e) { if(current === ticket && !abort.signal.aborted) error.value = e instanceof Error ? e.message : '匯出失敗。' }
  finally { if(current === ticket) { busy.value = false; controller = null } }
}
</script>
<template>
  <details class="experiment-planner"><summary>固定測試集與參數比較</summary>
    <p class="footnote">支援 checkpoint 文生圖與單張圖生圖；圖生圖每組沿用同一輸入。一次一個參數、1–4 個值、最多 8 次生成預覽；每個方案需分別載入並明確生成。</p>
    <SavedExperimentPlans :plan="plan" :disabled="props.disabled || busy" @busy="documentBusy = $event" @open="openPlan" />
    <label for="experiment-title">比較名稱</label><input id="experiment-title" v-model="title" maxlength="100" :disabled="blocked">
    <label for="experiment-axis">比較參數</label><select id="experiment-axis" v-model="axis" :disabled="blocked"><option value="steps">Steps</option><option value="cfg">CFG</option><option value="denoise" :disabled="settings.workflow_mode !== 'image2image'">Denoise（圖生圖改動幅度）</option><option value="seed">Seed（字串）</option><option value="lora_strength_model">LoRA 模型強度</option><option value="lora_strength_clip">LoRA CLIP 強度</option></select>
    <template v-if="isLoraAxis"><label for="experiment-lora">要比較的已啟用 LoRA</label><select id="experiment-lora" v-model="targetLora" :disabled="blocked"><option value="">請選擇 LoRA</option><option v-for="item in activeLoras" :key="item.name" :value="item.name">{{ item.name }}</option></select><p class="footnote">每次只改這個 LoRA 的一種強度，其餘強度、啟用狀態與順序保留。沒有已啟用的 LoRA 時，請先在創作設定加入。</p></template>
    <label for="experiment-values">參數值（JSON 陣列）</label><textarea id="experiment-values" v-model="values" rows="2" :disabled="blocked" aria-describedby="experiment-values-help"/><p id="experiment-values-help" class="footnote">例如 [4, 8] 或 [1, 5]；Seed 用 ["9007199254740993", "18446744073709551615"]。Denoise 例如 [0.3, 0.6]，範圍 0 至 1。LoRA 強度例如 [0.5, 1]；支援 -20 至 20，但實際可用範圍仍由生成前的引擎檢查決定。重複值及超界會拒絕。</p>
    <fieldset :disabled="blocked"><legend>固定案例（不選擇時沿用目前提示詞）</legend><template v-if="suite"><p class="footnote">{{ suite.name }} · v{{ suite.version }} · 相同角色案例需人工比較，未接入角色鎖定。</p><label v-for="item in suite.cases" :key="item.id" class="case-choice"><input v-model="caseIds" type="checkbox" :value="item.id" :aria-label="item.name">{{ item.name }}<span v-if="item.character_key"> · {{ item.character_key }}</span></label><details v-for="item in suite.cases" :key="item.id"><summary>{{ item.name }}：提示詞與評估要點</summary><p>{{ item.prompt }}</p><ul><li v-for="check in item.checks" :key="check">{{ check }}</li></ul></details></template></fieldset>
    <button type="button" class="secondary" :disabled="blocked" @click="preview">預覽比較方案</button>
    <p v-if="error" role="alert" class="notice warning">{{ error }}</p><p v-if="message" role="status" class="notice">{{ message }}</p>
    <section v-if="plan" aria-label="參數比較預覽"><h3>預計 {{ plan.expected_job_count }} 次生成 · 每次 1 張</h3>
      <p v-if="dirty" class="notice warning">目前有未保存變更；「載入這組設定」會取代目前表單，原已保存草稿及任務仍保留。</p>
      <p v-if="changed" class="footnote">目前表單已更動；下面仍是原比較方案的完整快照。要使用新的基準設定，請重新預覽。</p>
      <p v-if="plan.baseline.workflow_mode === 'image2image'" class="footnote">圖生圖來源：{{ plan.baseline.image_asset_id }} · {{ plan.baseline.reference_resize === 'fit' ? '等比補白' : '拉伸' }}；每組保留此輸入，生成前重新驗證素材。</p><p v-if="plan.target_lora" class="footnote">強度比較 LoRA：{{ plan.target_lora }}；原有順序保留。</p><ul><li v-for="warning in plan.warnings" :key="warning">{{ warning }}</li></ul><p class="footnote">方案 SHA256：{{ plan.plan_sha256 }}<span v-if="plan.suite"> · 測試集 v{{ plan.suite.version }} / {{ plan.suite.sha256 }}</span></p>
      <article v-for="variant in plan.variants" :key="variant.id" class="variant"><h4>{{ variant.id }} · {{ variant.case_id }} · {{ plan.axis }} = {{ variant.value }}</h4><p>{{ variant.settings.width }} × {{ variant.settings.height }} · {{ variant.settings.steps }} steps · CFG {{ variant.settings.cfg }} · Seed {{ variant.settings.seed }}<span v-if="variant.settings.workflow_mode === 'image2image'"> · Denoise {{ variant.settings.denoise }}</span></p><p>{{ variant.settings.prompt }}</p><details><summary>完整設定快照</summary><pre>{{ JSON.stringify(variant.settings,null,2) }}</pre></details><button type="button" class="secondary" :disabled="blocked" :aria-label="'載入比較設定 ' + variant.id" @click="apply(variant)">載入這組設定</button><span v-if="loaded.includes(variant.id)" class="footnote"> 已載入過；生成狀態請看任務區</span></article>
      <button type="button" class="secondary" :disabled="blocked" @click="exportPlan">匯出比較方案 JSON</button>
    </section>
    <a v-if="exportedUrl" :href="exportedUrl" download="model-atelier-comparison-plan.json">下載上次匯出的比較方案</a><details v-if="exported"><summary>上次匯出的完整比較 JSON</summary><pre>{{ exported }}</pre></details>
  </details>
</template>
<style scoped>
.experiment-planner{margin:20px 0;min-width:0;font-size:12px;overflow-wrap:anywhere}summary{cursor:pointer;color:var(--text-notice)}label{display:block;margin:16px 0 8px}input,select,textarea{box-sizing:border-box;width:100%;font:inherit;padding:10px}textarea{background:var(--surface-input);color:var(--text-primary);border:1px solid var(--border-control);border-radius:7px;resize:vertical}fieldset{margin:18px 0;border:1px solid var(--border-control);border-radius:8px}fieldset p{line-height:1.7}.case-choice{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.case-choice input{width:auto}button{margin:14px 0}ul{padding-left:20px;line-height:1.8}.variant{border:1px solid var(--border-control);padding:16px;border-radius:8px;margin:16px 0}h3{font-size:14px}h4{font-size:13px}pre{max-height:250px;overflow:auto;white-space:pre-wrap}a{display:block;margin:14px 0}
</style>
