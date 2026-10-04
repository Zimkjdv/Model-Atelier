<script setup lang="ts">
import { onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import type { LoraSetting } from './creationSettings'
type Parameters = { width: number; height: number; steps: number; cfg: number; sampler_name: string; scheduler: string; denoise: number; batch_size: number }
type Record = { id: string; date: string; model: string; lora: string; lora_version: string; strength_model: number; strength_clip: number; gpu: string; vram_bytes: number; ram_gib: number; os: string; python: string; comfyui: string; pytorch: string; driver: string; precision: string; offload: string; settings: Parameters; cold_wall_seconds: number; cold_engine_seconds: number; warm_engine_seconds: number | null; sampled_device_peak_bytes: number; sample_count: number; conditions: string; reference: string }
type Report = { engine_url: string; checkpoint: { name: string }; lora: { name: string }; status: 'recorded' | 'unverified' | 'incompatible'; message: string; registry_error: string | null; records: Record[]; matching_parameter_records: string[]; current_file_verified: false }
const props = defineProps<{ engineUrl: string; checkpoint: string; lora: LoraSetting; settings?: Parameters; refreshKey?: string; hasReferences?: boolean }>()
const report = ref<Report | null>(null), error = ref(''), busy = ref(false)
const labels = { recorded: '組合有實測紀錄', unverified: '組合尚未實測', incompatible: '登記架構不相容' }
let ticket = 0, controller: AbortController | null = null
const gib = (bytes: number) => `${(bytes / 1024 ** 3).toFixed(2)} GiB`
const referenceUrl = (path: string) => /^docs\/validation\/[a-z0-9-]+\.md$/.test(path) ? 'https://github.com/Zimkjdv/Model-Atelier/blob/main/' + path : ''
function cancel() { ++ticket; controller?.abort(); controller = null; busy.value = false; report.value = null }
async function load() {
  cancel(); error.value = ''
  if (!props.engineUrl || !props.checkpoint || !props.lora.enabled) return
  const token = ticket, engine = props.engineUrl, checkpoint = props.checkpoint, name = props.lora.name
  const abort = new AbortController(); controller = abort; busy.value = true
  try {
    const response = await fetch('/api/loras/validation', { method: 'POST', signal: abort.signal,
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ engine_url: engine, checkpoint, lora: props.lora, settings: props.settings ?? null }) })
    const value: Report = await response.json()
    if (!response.ok) throw new Error(response.status === 409 ? '引擎或登記資料已變更，請重新讀取。' : '無法查詢組合紀錄，請確認模型庫與參數後更新。')
    if (value.engine_url !== engine || value.checkpoint?.name !== checkpoint || value.lora?.name !== name ||
        !Object.hasOwn(labels, value.status) || !Array.isArray(value.records) || !Array.isArray(value.matching_parameter_records) ||
        value.current_file_verified !== false) throw new Error('組合紀錄來源不符，狀態保持未知。')
    if (token === ticket) report.value = value
  } catch (e) { if (token === ticket && !abort.signal.aborted) error.value = e instanceof Error ? e.message : '查詢失敗。' }
  finally { if (token === ticket) { busy.value = false; controller = null } }
}
watch(() => JSON.stringify([props.engineUrl, props.checkpoint, props.lora, props.settings, props.refreshKey]), () => { void load() }, { immediate: true })
onActivated(() => { void load() })
onDeactivated(cancel)
onBeforeUnmount(cancel)
</script>

<template>
  <section class="lora-validation" aria-label="單一 LoRA 組合實測紀錄">
    <div class="evidence-heading"><h3>單一 LoRA 組合實測</h3><button type="button" class="secondary" :disabled="busy" @click="load">{{ busy ? '讀取中…' : '更新組合紀錄' }}</button></div>
    <p v-if="error" role="alert">{{ error }} 原參數仍保留。</p>
    <template v-if="report">
      <strong>{{ labels[report.status] }}</strong><p>{{ report.message }}</p>
      <p v-if="report.registry_error" role="alert">{{ report.registry_error }}</p>
      <p v-if="settings" class="parameter-match" role="status">{{ report.matching_parameter_records.length ? '目前強度與取樣參數符合歷史實測條件；不是本次生成或硬體保證。' : '目前強度或取樣參數沒有匹配的實測紀錄。' }}</p>
      <p v-if="hasReferences" class="footnote">實測未使用參考圖；目前參考素材僅保存，尚未接入生成流程。</p>
      <details v-for="record in report.records" :key="record.id"><summary>{{ record.model }} + {{ record.lora }} · {{ record.gpu }} · {{ record.date }}</summary>
        <dl><dt>LoRA 版本與強度</dt><dd>{{ record.lora_version }} · model {{ record.strength_model }} / CLIP {{ record.strength_clip }}</dd>
          <dt>取樣設定</dt><dd>{{ record.settings.width }} × {{ record.settings.height }} · {{ record.settings.steps }} steps · CFG {{ record.settings.cfg }} · {{ record.settings.sampler_name }} / {{ record.settings.scheduler }} · denoise {{ record.settings.denoise }} · batch {{ record.settings.batch_size }}</dd>
          <dt>硬體與系統</dt><dd>{{ record.gpu }} · VRAM {{ gib(record.vram_bytes) }} · RAM {{ record.ram_gib }} GiB · {{ record.os }}</dd>
          <dt>執行環境</dt><dd>ComfyUI {{ record.comfyui }} · Python {{ record.python }} · PyTorch {{ record.pytorch }} · 驅動 {{ record.driver }}</dd>
          <dt>精度與卸載</dt><dd>{{ record.precision }}；{{ record.offload }}</dd>
          <dt>冷啟動平台耗時</dt><dd>{{ record.cold_wall_seconds }} 秒（提交至觀察成功，含載入與查詢）</dd>
          <dt>冷啟動引擎耗時</dt><dd>{{ record.cold_engine_seconds }} 秒（不同量測定義）</dd>
          <dt>暖機耗時</dt><dd>{{ record.warm_engine_seconds === null ? '未量測' : record.warm_engine_seconds + ' 秒' }}</dd>
          <dt>整卡取樣最高用量</dt><dd>{{ gib(record.sampled_device_peak_bytes) }} · {{ record.sample_count }} 次取樣；不是最低需求</dd>
        </dl><p>{{ record.conditions }}</p><a v-if="referenceUrl(record.reference)" :href="referenceUrl(record.reference)" target="_blank" rel="noopener noreferrer">查看 LoRA 完整驗收紀錄 ↗</a>
      </details>
      <p class="footnote">只比對兩份登記 SHA256 與架構，不讀取當前權重、不載入 GPU、不改設定。訓練、其他 LoRA 或 RTX 4080 尚未驗證。</p>
    </template>
  </section>
</template>

<style scoped>
.lora-validation{border:1px solid var(--border-notice);background:var(--surface-notice);border-radius:var(--radius-control);padding:16px;margin:18px 0;overflow-wrap:anywhere}.evidence-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.evidence-heading h3{margin:0;font-size:14px}.evidence-heading button{font-size:11px}.lora-validation p,.lora-validation summary{font-size:12px;line-height:1.8}.lora-validation strong,.parameter-match{color:var(--text-notice)}summary{cursor:pointer}details{margin:14px 0}dl{display:grid;grid-template-columns:125px minmax(0,1fr);gap:10px;font-size:11px;line-height:1.7}dt{color:var(--text-muted)}dd{margin:0}a{font-size:12px;color:var(--text-notice)}@media(max-width:700px){dl{grid-template-columns:1fr;gap:6px}dd{margin-bottom:8px}}
</style>
