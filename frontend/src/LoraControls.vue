<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { LoraSetting } from './creationSettings'
import { architectureLabel } from './modelMetadata'

type Catalog = { engine_url: string; synced_at: string | null; sync_error: string | null;
  loras: { name: string; listed: boolean; version: string; architecture: string }[] }
const props = defineProps<{ modelValue: LoraSetting[]; engineUrl: string; checkpoint: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: LoraSetting[]]; blocked: [reason: string] }>()
const catalog = ref<Catalog | null>(null), busy = ref(false), error = ref('')
const chosen = computed(() => props.modelValue[0])
const record = computed(() => catalog.value?.loras.find(item => item.name === chosen.value?.name))
const choices = computed(() => catalog.value?.loras.filter(item => item.listed) ?? [])
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
function choose(event: Event) {
  const name = (event.target as HTMLSelectElement).value
  emit('update:modelValue', name ? [{ name, enabled: true, strength_model: 1, strength_clip: 1 }] : [])
}
function update(values: Partial<LoraSetting>) {
  if (chosen.value) emit('update:modelValue', [{ ...chosen.value, ...values }])
}
watch(() => props.engineUrl, () => { void load() }, { immediate: true })
watch(() => chosen.value?.enabled, enabled => emit('blocked', enabled ? 'LoRA 設定可保存草稿，尚未接入生成流程；請先停用 LoRA 再生成。' : ''), { immediate: true })
onBeforeUnmount(() => { ++revision; controller?.abort() })
</script>

<template>
  <section class="lora-controls" aria-labelledby="creation-lora-heading">
    <div class="lora-heading"><h3 id="creation-lora-heading">LoRA 設定</h3><button type="button" class="secondary" :disabled="busy" @click="load">更新 LoRA 選項</button></div>
    <p id="creation-lora-help" class="footnote">第一版保存單一 LoRA；選擇不會載入權重。目前生成流程尚未接入 LoRA，停用後才能生成。</p>
    <p v-if="error" role="alert" class="notice warning">{{ error }}</p>
    <p v-if="catalog?.sync_error" role="status" class="notice warning">{{ catalog.sync_error }} 選項為歷史快照。</p>
    <label for="creation-lora">LoRA 模型</label>
    <select id="creation-lora" :value="chosen?.name ?? ''" :disabled="busy || !catalog" aria-describedby="creation-lora-help" @change="choose">
      <option value="">不使用 LoRA</option>
      <option v-if="chosen && !choices.some(item => item.name === chosen.name)" :value="chosen.name">{{ chosen.name }}（原設定，清單尚未確認）</option>
      <option v-for="item in choices" :key="item.name" :value="item.name">{{ item.name }} · {{ item.version.trim() || '版本未知' }}</option>
    </select>
    <p v-if="busy" role="status" class="footnote">正在讀取 LoRA 登記選項…</p>
    <p v-else-if="catalog && !choices.length" class="footnote">最近清單沒有 LoRA；請先在模型庫同步。原選擇及強度仍保留。</p>
    <template v-if="chosen">
      <p class="footnote">登記基礎架構：{{ architectureLabel(record?.architecture) }} · 版本 {{ record?.version.trim() || '未知' }}；不是權重驗證。</p>
      <label class="lora-toggle"><input type="checkbox" :checked="chosen.enabled" @change="update({ enabled: ($event.target as HTMLInputElement).checked })">啟用此 LoRA</label>
      <div class="lora-strengths">
        <label for="lora-model-strength">模型強度<input id="lora-model-strength" :value="chosen.strength_model" type="number" min="-20" max="20" step="any" required aria-describedby="lora-strength-help" @input="update({ strength_model: ($event.target as HTMLInputElement).valueAsNumber })"></label>
        <label for="lora-clip-strength">CLIP 強度<input id="lora-clip-strength" :value="chosen.strength_clip" type="number" min="-20" max="20" step="any" required aria-describedby="lora-strength-help" @input="update({ strength_clip: ($event.target as HTMLInputElement).valueAsNumber })"></label>
      </div>
      <p id="lora-strength-help" class="footnote">平台範圍 −20 至 20，允許負值及 0；停用時保留強度，移除時清除此草稿的 LoRA 設定。</p>
      <button type="button" class="secondary" @click="emit('update:modelValue', [])">移除此 LoRA</button>
    </template>
  </section>
</template>

<style scoped>
.lora-controls{border-top:1px solid var(--border-control);margin-top:24px;padding-top:20px;min-width:0}.lora-heading{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}.lora-heading h3{margin:0;font-size:14px}.lora-heading button{font-size:11px;padding:8px 10px}.lora-controls label{display:block;font-size:12px;margin:16px 0 8px}.lora-controls select{width:100%;min-width:0;box-sizing:border-box;padding:12px}.lora-controls .lora-toggle{display:flex;gap:10px;align-items:center}.lora-toggle input{width:16px;flex-shrink:0}.lora-strengths{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.lora-strengths input{width:100%;min-width:0;box-sizing:border-box;padding:12px;margin-top:8px}.lora-controls p{overflow-wrap:anywhere}
</style>
