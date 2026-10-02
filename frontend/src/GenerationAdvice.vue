<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import type { CreationForm } from './creationSettings'
const props = defineProps<{ form: CreationForm }>()
type Report = { checked_at: string; warnings: string[]; diagnostics: { status: string; devices: { name: string | null; vram: { total: number | null; free: number | null } }[] } }
const report = ref<Report | null>(null), error = ref(''), busy = ref(false)
let request = 0, controller: AbortController | null = null
function reset() { ++request; controller?.abort(); report.value = null; error.value = ''; busy.value = false }
watch(() => JSON.stringify(props.form), reset)
onBeforeUnmount(reset)
const gib = (value: number | null) => value === null ? '未知' : `${(value / 1024 ** 3).toFixed(2)} GiB`
async function check() {
  reset(); const token = request; controller = new AbortController(); busy.value = true
  const { engine_url, checkpoint, width, height, steps, cfg, sampler_name, scheduler, denoise } = props.form
  try {
    const response = await fetch('/api/generation-advice', { method: 'POST', signal: controller.signal,
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ engine_url, checkpoint, width, height, steps, cfg, sampler_name, scheduler, denoise }) })
    if (!response.ok) throw new Error(response.status === 409 ? '模型或引擎已變更，請重新載入後查詢。' : '提示暫時無法取得，請確認模型與參數後重試。')
    const value = await response.json()
    if (token === request) report.value = value
  } catch (e) { if (token === request) error.value = e instanceof Error ? e.message : '查詢失敗' }
  finally { if (token === request) busy.value = false }
}
</script>
<template>
  <section class="resource-advice" aria-label="生成資源提示">
    <h3>資源與驗證提示</h3>
    <p>查詢選取引擎的可用顯存及目前參數的實測範圍。提示不會修改設定或限制生成。</p>
    <button type="button" :disabled="busy || !form.checkpoint" @click="check">{{ busy ? '查詢中…' : '查看資源與驗證提示' }}</button>
    <p v-if="error" role="alert">{{ error }}</p>
    <div v-if="report" aria-live="polite">
      <small>{{ form.engine_url }} · {{ new Date(report.checked_at).toLocaleString() }}</small>
      <p v-for="(device, i) in report.diagnostics.devices" :key="i">{{ device.name || '未知裝置' }}：可用 {{ gib(device.vram.free) }} / 總計 {{ gib(device.vram.total) }}</p>
      <ul><li v-for="warning in report.warnings" :key="warning">{{ warning }}</li></ul>
    </div>
  </section>
</template>
<style scoped>
.resource-advice { margin: 16px 0; padding: 18px; border: 1px solid #405047; border-radius: 12px; background: #19231e; }
h3 { margin: 0 0 8px; } p, li { line-height: 1.7; } small { display: block; margin-top: 12px; overflow-wrap: anywhere; }
</style>
