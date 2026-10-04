<script setup lang="ts">
import { onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import type { LoraSetting } from './creationSettings'
type Parameters = { width: number; height: number; steps: number; cfg: number; sampler_name: string; scheduler: string; denoise: number; batch_size: number }
type Evidence = { id: string; date: string; gpu: string; comfyui: string; pytorch: string; precision: string; offload: string; settings: Parameters; wall_seconds: number; engine_seconds: number; load_condition: string; sampled_device_peak_bytes: number; sample_count: number; quality_observation: string; conditions: string; reference: string; loras: { name: string; version: string; strength_model: number; strength_clip: number }[] }
type Report = { engine_url: string; checkpoint: { name: string }; status: 'recorded' | 'unverified' | 'incompatible'; message: string; registry_error: string | null; matching_parameter_records: string[]; records: Evidence[]; current_file_verified: false }
const props = defineProps<{ engineUrl: string; checkpoint: string; loras: LoraSetting[]; settings: Parameters; refreshKey?: string }>()
const report = ref<Report | null>(null), error = ref(''), busy = ref(false)
let ticket = 0, controller: AbortController | null = null
const labels = { recorded: '有序組合有載入紀錄', unverified: '有序組合未驗證', incompatible: '登記架構不相容' }
function cancel() { ++ticket; controller?.abort(); controller = null; report.value = null; busy.value = false }
async function load() {
  cancel(); error.value = ''
  if (!props.engineUrl || !props.checkpoint) return
  const token = ticket, abort = new AbortController(); controller = abort; busy.value = true
  try {
    const response = await fetch('/api/loras/stack-validation', { method: 'POST', signal: abort.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ engine_url: props.engineUrl, checkpoint: props.checkpoint, loras: props.loras, settings: props.settings }) })
    const value: Report = await response.json()
    if (!response.ok) throw new Error(response.status === 409 ? '引擎或登記已變更，請重新讀取。' : '無法讀取有序組合，請確認清單與參數。')
    if (value.engine_url !== props.engineUrl || value.checkpoint?.name !== props.checkpoint || !Object.hasOwn(labels, value.status) || value.current_file_verified !== false || !Array.isArray(value.records)) throw new Error('紀錄來源不符，保持未知。')
    if (ticket === token) report.value = value
  } catch(e) { if (ticket === token && !abort.signal.aborted) error.value = e instanceof Error ? e.message : '讀取失敗。' }
  finally { if (ticket === token) { busy.value = false; controller = null } }
}
watch(() => JSON.stringify([props.engineUrl, props.checkpoint, props.loras, props.settings, props.refreshKey]), () => { void load() }, { immediate: true })
onActivated(() => { void load() }); onDeactivated(cancel); onBeforeUnmount(cancel)
const link = (v: string) => /^docs\/validation\/[a-z0-9-]+\.md$/.test(v) ? 'https://github.com/Zimkjdv/Model-Atelier/blob/main/' + v : ''
</script>
<template>
  <section class="stack-evidence" aria-label="有序 LoRA 組合實測紀錄">
    <h3>有序 LoRA 組合實測</h3><button type="button" class="secondary" :disabled="busy" @click="load">更新有序組合紀錄</button>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="report"><strong>{{ labels[report.status] }}</strong><p>{{ report.message }}</p>
      <p v-if="report.registry_error" role="alert">{{ report.registry_error }}</p>
      <p role="status">{{ report.matching_parameter_records.length ? '目前順序、強度及取樣參數符合歷史條件；不是本次生成或品質保證。' : '目前強度或取樣參數沒有匹配紀錄。' }}</p>
      <details v-for="record in report.records" :key="record.id"><summary>{{ record.gpu }} · {{ record.date }} · 查看條件及品質觀察</summary>
        <ol><li v-for="(lora, i) in record.loras" :key="i">{{ lora.name }} · {{ lora.version }} · model {{ lora.strength_model }} / CLIP {{ lora.strength_clip }}</li></ol>
        <p>{{ record.settings.width }} × {{ record.settings.height }} · {{ record.settings.steps }} steps · CFG {{ record.settings.cfg }} · {{ record.settings.sampler_name }} / {{ record.settings.scheduler }} · denoise {{ record.settings.denoise }} · batch {{ record.settings.batch_size }}</p>
        <p>ComfyUI {{ record.comfyui }} · PyTorch {{ record.pytorch }} · {{ record.precision }}；{{ record.offload }}</p>
        <p>平台觀察 {{ record.wall_seconds }} 秒／引擎日誌 {{ record.engine_seconds }} 秒；{{ record.load_condition }}</p>
        <p>整卡取樣最高 {{ (record.sampled_device_peak_bytes / 1024 ** 3).toFixed(2) }} GiB · {{ record.sample_count }} 筆；非最低需求。</p>
        <p class="notice warning">品質觀察：{{ record.quality_observation }}</p><p>{{ record.conditions }}</p>
        <a v-if="link(record.reference)" :href="link(record.reference)" target="_blank" rel="noopener noreferrer">完整驗收紀錄 ↗</a>
      </details><p class="footnote">只讀登記雜湊；不驗當前權重、不載入 GPU、不改設定。圖生圖、訓練及 RTX 4080 未驗證。</p>
    </template>
  </section>
</template>
<style scoped>
.stack-evidence{border:1px solid var(--border-notice);padding:16px;margin:18px 0;border-radius:var(--radius-control);font-size:12px;line-height:1.8;overflow-wrap:anywhere}.stack-evidence h3{font-size:14px}strong{display:block;color:var(--text-notice);margin-top:12px}summary{cursor:pointer}details{margin:14px 0}
</style>
