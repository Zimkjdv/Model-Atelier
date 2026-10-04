<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import type { LoraSetting } from './creationSettings'
import { architectureLabel } from './modelMetadata'

type Catalog = { engine_url: string; synced_at: string | null; sync_error: string | null;
  loras: { name: string; listed: boolean; version: string; architecture: string }[] }
const props = defineProps<{ modelValue: LoraSetting[]; engineUrl: string; checkpoint: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: LoraSetting[]]; blocked: [reason: string] }>()
const catalog = ref<Catalog | null>(null), busy = ref(false), error = ref('')
const newName = ref('')
const active = computed(() => props.modelValue.filter(item => item.enabled))
const record = (name: string) => catalog.value?.loras.find(item => item.name === name)
const choices = computed(() => catalog.value?.loras.filter(item => item.listed && !props.modelValue.some(chosen => chosen.name === item.name)) ?? [])
type Assessment = { engine_url: string; checkpoint: { name: string }; loras: { name: string; status: string; label: string; message: string; verified: false }[] }
const assessment = ref<Assessment | null>(null), assessmentBusy = ref(false), assessmentError = ref('')
const comparison = (name: string) => assessment.value?.loras.find(item => item.name === name)
let assessmentRevision = 0, assessmentAbort: AbortController | null = null
async function assess() {
  const ticket = ++assessmentRevision, url = props.engineUrl, checkpoint = props.checkpoint
  assessmentAbort?.abort(); assessment.value = null; assessmentError.value = ''; assessmentBusy.value = false
  if (!active.value.length || !url || !checkpoint) return
  const abort = new AbortController(); assessmentAbort = abort; assessmentBusy.value = true
  try {
    const response = await fetch('/api/loras/compatibility?' + new URLSearchParams({ engine_url: url, checkpoint }), { signal: abort.signal })
    if (!response.ok) throw new Error('無法取得登記架構比較；生成前仍會重新檢查，請先確認模型庫。')
    const value: Assessment = await response.json()
    if (value.engine_url !== url || value.checkpoint?.name !== checkpoint || !Array.isArray(value.loras) ||
        !value.loras.every(item => item.verified === false && ['compatible', 'unverified', 'incompatible'].includes(item.status)))
      throw new Error('LoRA 架構比較資料無效，請重新更新。')
    if (ticket === assessmentRevision) assessment.value = value
  } catch (e) { if (ticket === assessmentRevision && !abort.signal.aborted) assessmentError.value = e instanceof Error ? e.message : '架構比較失敗。' }
  finally { if (ticket === assessmentRevision) { assessmentBusy.value = false; assessmentAbort = null } }
}
const block = computed(() => {
  if (props.modelValue.length > 4 || new Set(props.modelValue.map(item => item.name)).size !== props.modelValue.length) return '最多選擇四個不同的 LoRA。'
  if (props.modelValue.some(item => !Number.isFinite(item.strength_model) || !Number.isFinite(item.strength_clip) || Math.abs(item.strength_model) > 20 || Math.abs(item.strength_clip) > 20)) return 'LoRA 強度需為 −20 至 20 的有限數值。'
  if (!active.value.length) return ''
  if (assessmentBusy.value) return '正在讀取 LoRA 登記架構比較，請稍候。'
  const incompatible = active.value.find(item => comparison(item.name)?.status === 'incompatible')
  return incompatible ? `${incompatible.name}：${comparison(incompatible.name)!.message}` : ''
})
let revision = 0, controller: AbortController | null = null
async function load() {
  const ticket = ++revision, url = props.engineUrl
  controller?.abort(); controller = null; catalog.value = null; error.value = ''; busy.value = false
  if (!url) return
  const abort = new AbortController(); controller = abort; busy.value = true
  try {
    const response = await fetch('/api/loras', { signal: abort.signal })
    if (!response.ok) throw new Error('無法讀取 LoRA 模型庫，原設定仍保留。')
    const value: Catalog = await response.json()
    if (value.engine_url !== url || !Array.isArray(value.loras)) throw new Error('草稿引擎與目前 LoRA 模型庫不同；請確認設定後更新。')
    if (ticket === revision && props.engineUrl === url) catalog.value = value
  } catch (e) { if (ticket === revision && !abort.signal.aborted) error.value = e instanceof Error ? e.message : 'LoRA 清單讀取失敗。' }
  finally { if (ticket === revision) { busy.value = false; controller = null } }
}
function add() {
  if (!choices.value.some(item => item.name === newName.value) || props.modelValue.length >= 4) return
  emit('update:modelValue', [...props.modelValue, { name: newName.value, enabled: true, strength_model: 1, strength_clip: 1 }])
  newName.value = ''
}
function update(index: number, values: Partial<LoraSetting>) {
  emit('update:modelValue', props.modelValue.map((item, current) => current === index ? { ...item, ...values } : { ...item }))
}
function remove(index: number) { emit('update:modelValue', props.modelValue.filter((_, current) => current !== index).map(item => ({ ...item }))) }
function move(index: number, direction: number) {
  const values = props.modelValue.map(item => ({ ...item })), target = index + direction
  if (target < 0 || target >= values.length) return
  ;[values[index], values[target]] = [values[target]!, values[index]!]
  emit('update:modelValue', values)
}
watch(() => props.engineUrl, () => { void load() }, { immediate: true })
watch(() => [props.engineUrl, props.checkpoint, JSON.stringify(props.modelValue.map(item => [item.name, item.enabled])), catalog.value], () => { void assess() }, { immediate: true })
watch(block, reason => emit('blocked', reason), { immediate: true })
function cancelRequests() { ++revision; ++assessmentRevision; controller?.abort(); assessmentAbort?.abort(); busy.value = false; assessmentBusy.value = false }
onActivated(() => { void load() })
onDeactivated(cancelRequests)
onBeforeUnmount(cancelRequests)
</script>

<template>
  <section class="lora-controls" aria-labelledby="creation-lora-heading">
    <div class="lora-heading"><h3 id="creation-lora-heading">LoRA 設定</h3><button type="button" class="secondary" :disabled="busy" @click="load">更新 LoRA 選項</button></div>
    <p id="creation-lora-help" class="footnote">最多四個不同 LoRA，由上至下串接 MODEL 與 CLIP；順序會影響結果。選擇不載入權重；生成前逐個檢查登記架構、即時名稱與強度。多 LoRA 尚未有可自動匹配的組合實測紀錄，畫面效果需依目前順序與強度確認。</p>
    <p v-if="error" role="alert" class="notice warning">{{ error }}</p>
    <p v-if="catalog?.sync_error" role="status" class="notice warning">{{ catalog.sync_error }} 選項為歷史快照。</p>
    <label for="creation-lora">新增 LoRA</label>
    <select id="creation-lora" v-model="newName" :disabled="busy || !catalog || modelValue.length >= 4" aria-describedby="creation-lora-help">
      <option value="">選擇要加入的模型</option>
      <option v-for="item in choices" :key="item.name" :value="item.name">{{ item.name }} · {{ item.version.trim() || '版本未知' }}</option>
    </select>
    <button type="button" class="secondary" :disabled="busy || !choices.some(item => item.name === newName) || modelValue.length >= 4" @click="add">加入 LoRA</button>
    <p class="footnote" role="status">已選 {{ modelValue.length }} / 4 · 啟用 {{ active.length }} 個</p>
    <p v-if="busy" role="status" class="footnote">正在讀取 LoRA 登記選項…</p>
    <p v-else-if="catalog && !catalog.loras.some(item => item.listed)" class="footnote">最近清單沒有 LoRA；請先在模型庫同步。原選擇及強度仍保留。</p>
    <article v-for="(chosen, index) in modelValue" :key="chosen.name" class="lora-item" :aria-label="`LoRA ${index + 1}：${chosen.name}`">
      <h4>{{ index + 1 }}. {{ chosen.name }}</h4>
      <p class="footnote">登記基礎架構：{{ architectureLabel(record(chosen.name)?.architecture) }} · 版本 {{ record(chosen.name)?.version.trim() || '未知' }}；不是權重驗證。{{ record(chosen.name)?.listed ? '' : '原設定，清單尚未確認。' }}</p>
      <label class="lora-toggle"><input type="checkbox" :checked="chosen.enabled" :aria-label="`啟用 LoRA ${index + 1}`" @change="update(index, { enabled: ($event.target as HTMLInputElement).checked })">啟用此 LoRA</label>
      <p v-if="chosen.enabled && assessmentBusy" role="status" class="footnote">正在比較登記架構…</p>
      <p v-else-if="chosen.enabled" role="status" class="notice" :class="{ warning: comparison(chosen.name)?.status === 'incompatible' }">{{ assessmentError || (comparison(chosen.name) ? comparison(chosen.name)!.label + '：' + comparison(chosen.name)!.message : 'LoRA 架構未驗證；生成前由引擎再次檢查。') }}</p>
      <div class="lora-strengths">
        <label :for="`lora-model-strength-${index}`">模型強度<input :id="`lora-model-strength-${index}`" :aria-label="`LoRA ${index + 1} 模型強度`" :value="chosen.strength_model" type="number" min="-20" max="20" step="any" required aria-describedby="lora-strength-help" @input="update(index, { strength_model: ($event.target as HTMLInputElement).valueAsNumber })"></label>
        <label :for="`lora-clip-strength-${index}`">CLIP 強度<input :id="`lora-clip-strength-${index}`" :aria-label="`LoRA ${index + 1} CLIP 強度`" :value="chosen.strength_clip" type="number" min="-20" max="20" step="any" required aria-describedby="lora-strength-help" @input="update(index, { strength_clip: ($event.target as HTMLInputElement).valueAsNumber })"></label>
      </div>
      <button type="button" class="secondary" :disabled="index === 0" :aria-label="`上移 LoRA ${index + 1}`" @click="move(index, -1)">上移</button>
      <button type="button" class="secondary" :disabled="index === modelValue.length - 1" :aria-label="`下移 LoRA ${index + 1}`" @click="move(index, 1)">下移</button>
      <button type="button" class="secondary" :aria-label="`移除 LoRA ${index + 1}`" @click="remove(index)">移除此 LoRA</button>
    </article>
    <p id="lora-strength-help" class="footnote">強度範圍 −20 至 20，允許負值及 0；停用保留設定且不進入流程，移除只清除此草稿的項目。</p>
  </section>
</template>

<style scoped>
.lora-item{border:1px solid var(--border-control);border-radius:8px;padding:12px;margin:12px 0;min-width:0}.lora-item h4{font-size:12px;overflow-wrap:anywhere;margin:0}.lora-item button{margin:8px 8px 0 0;font-size:11px}
.lora-controls{border-top:1px solid var(--border-control);margin-top:24px;padding-top:20px;min-width:0}.lora-heading{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}.lora-heading h3{margin:0;font-size:14px}.lora-heading button{font-size:11px;padding:8px 10px}.lora-controls label{display:block;font-size:12px;margin:16px 0 8px}.lora-controls select{width:100%;min-width:0;box-sizing:border-box;padding:12px}.lora-controls .lora-toggle{display:flex;gap:10px;align-items:center}.lora-toggle input{width:16px;flex-shrink:0}.lora-strengths{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.lora-strengths input{width:100%;min-width:0;box-sizing:border-box;padding:12px;margin-top:8px}.lora-controls p{overflow-wrap:anywhere}
</style>
