<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
type Record = { id: string; date: string; model: string; gpu: string; vram_bytes: number; ram_gib: number; os: string; python: string; comfyui: string; pytorch: string; driver: string; precision: string; offload: string; settings: { width: number; height: number; steps: number; cfg: number; sampler_name: string; scheduler: string; denoise: number; batch_size: number }; cold_wall_seconds: number; warm_engine_seconds: number; sampled_device_peak_bytes: number; sample_count: number; reference: string; conditions: string }
type Report = { engine_url: string; name: string; status: 'verified' | 'unverified' | 'incompatible'; message: string; registry_error: string | null; records: Record[] }
const props = defineProps<{ engineUrl: string; name: string; refreshKey?: string }>()
const report = ref<Report | null>(null), error = ref(''), busy = ref(false)
let token = 0, controller: AbortController | undefined
const labels = { verified: '記錄條件下已驗證', unverified: '尚未驗證', incompatible: '目前流程不相容' }
const gib = (n: number) => `${(n / 1024 ** 3).toFixed(2)} GiB`
const referenceUrl = (path: string) => /^docs\/validation\/[a-z0-9-]+\.md$/.test(path) ? 'https://github.com/Zimkjdv/Model-Atelier/blob/main/' + path : ''
async function load() {
  const request = ++token, engine = props.engineUrl, name = props.name
  controller?.abort(); controller = new AbortController(); report.value = null; error.value = ''; busy.value = true
  try {
    const response = await fetch('/api/models/validation?' + new URLSearchParams({ engine_url: engine, name }), { signal: controller.signal })
    const data = await response.json()
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '無法讀取驗證紀錄。')
    if (data.engine_url !== engine || data.name !== name || !Array.isArray(data.records) || !Object.hasOwn(labels, data.status)) throw new Error('驗證紀錄來源不符，請重新讀取。')
    if (request === token) report.value = data
  } catch (e) { if (request === token) error.value = e instanceof Error ? e.message : '無法讀取驗證紀錄。' }
  finally { if (request === token) busy.value = false }
}
watch(() => [props.engineUrl, props.name, props.refreshKey], load, { immediate: true })
onBeforeUnmount(() => { ++token; controller?.abort() })
</script>

<template>
  <section class="validation-records" aria-label="模型與流程驗證紀錄">
    <div class="validation-heading"><h3>流程驗證紀錄</h3><button type="button" class="secondary" :disabled="busy" @click="load">{{ busy ? '讀取中…' : '更新驗證紀錄' }}</button></div>
    <p v-if="error" role="alert">{{ error }} 狀態保持未知，這不影響保存草稿。</p>
    <template v-if="report">
      <strong>{{ labels[report.status] }}</strong><p>{{ report.message }}</p>
      <p v-if="report.registry_error" role="alert">{{ report.registry_error }}</p>
      <details v-for="record in report.records" :key="record.id"><summary>{{ record.model }} · {{ record.gpu }} · {{ record.date }}</summary>
        <dl><dt>測試流程</dt><dd>標準 checkpoint 單張文生圖；訓練尚未驗證</dd>
          <dt>設定</dt><dd>{{ record.settings.width }} × {{ record.settings.height }} · {{ record.settings.steps }} steps · CFG {{ record.settings.cfg }} · {{ record.settings.sampler_name }} / {{ record.settings.scheduler }} · denoise {{ record.settings.denoise }} · batch {{ record.settings.batch_size }}</dd>
          <dt>硬體與系統</dt><dd>VRAM {{ gib(record.vram_bytes) }} · RAM {{ record.ram_gib }} GiB · {{ record.os }}</dd>
          <dt>執行環境</dt><dd>ComfyUI {{ record.comfyui }} · Python {{ record.python }} · PyTorch {{ record.pytorch }} · 驅動 {{ record.driver }}</dd>
          <dt>精度與卸載</dt><dd>{{ record.precision }}；{{ record.offload }}</dd>
          <dt>首次平台耗時</dt><dd>{{ record.cold_wall_seconds }} 秒（含冷載入與查詢）</dd>
          <dt>暖啟動引擎耗時</dt><dd>{{ record.warm_engine_seconds }} 秒（不同量測定義）</dd>
          <dt>整卡取樣最高用量</dt><dd>{{ gib(record.sampled_device_peak_bytes) }} · {{ record.sample_count }} 次取樣；不是最低需求</dd>
        </dl><p>{{ record.conditions }}</p><a v-if="referenceUrl(record.reference)" :href="referenceUrl(record.reference)" target="_blank" rel="noopener noreferrer">查看完整驗收紀錄 ↗</a>
      </details>
      <p class="footnote">以登記的 SHA256 與架構比對紀錄；本次查詢不驗證實際權重，不代表目前硬體、參數或訓練已通過。</p>
    </template>
  </section>
</template>

<style scoped>
.validation-records{border:1px solid #405047;background:#19231e;border-radius:9px;padding:16px;margin:18px 0;overflow-wrap:anywhere}.validation-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px}.validation-heading h3{font-size:13px;margin:0}.validation-heading button{font-size:11px}.validation-records strong{font-size:12px;color:#cee0c4}details{margin:14px 0;font-size:12px}summary{cursor:pointer;color:#c0d4b4;line-height:1.8}dl{display:grid;grid-template-columns:130px 1fr;gap:12px;font-size:11px}dt{color:#96a59b}dd{margin:0}a{color:#c0d4b4;font-size:12px}@media(max-width:700px){dl{grid-template-columns:1fr;gap:7px}dd{margin-bottom:8px}.validation-heading{flex-wrap:wrap}}
</style>
