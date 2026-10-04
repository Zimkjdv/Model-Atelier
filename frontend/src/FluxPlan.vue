<script setup lang="ts">
import { onMounted, onBeforeUnmount, onDeactivated, ref } from 'vue'
type Plan = {
  id: string; name: string; verified_at: string; checked_at: string; source_url: string; reference_url: string
  license: { name: string; url: string; note: string }; total_size_bytes: number
  space_status: 'sufficient' | 'insufficient' | 'unknown'; generation_supported: false; download_supported: false
  current_files_verified: false; warnings: string[]
  components: { role: string; name: string; filename: string; version: string; revision: string; sha256: string
    size_bytes: number; state: string; actual_size_bytes: number | null; target: string; precision: string
    access: string; license_name: string; provenance: string; source_url: string; error: string | null }[]
  volumes: { id: string; path: string; free_bytes: number; required_bytes: number }[]
}
const plan = ref<Plan | null>(null), busy = ref(false), error = ref('')
const gib = (bytes: number) => (bytes / 1024 ** 3).toFixed(2) + ' GiB'
const states: Record<string, string> = {missing:'尚無檔案',present_unverified:'同大小檔案，尚未驗檔',size_mismatch:'檔案大小不符',unknown:'路徑／狀態未知'}
const spaces = {sufficient:'磁碟預算足夠，安裝與生成仍待接入',insufficient:'本機磁碟空間不足',unknown:'本機磁碟容量未知'}
let ticket = 0, controller: AbortController | null = null
async function load() {
  const current = ++ticket
  controller?.abort(); plan.value = null; error.value = ''; busy.value = true
  const abort = new AbortController(); controller = abort
  try {
    const response = await fetch('/api/model-plans/flux1-schnell',{signal:abort.signal})
    const value = await response.json()
    if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'FLUX 計畫暫時無法讀取。')
    if (value.id !== 'flux1-schnell' || value.generation_supported !== false || value.download_supported !== false ||
        value.current_files_verified !== false || !Array.isArray(value.components) || value.components.length !== 4 ||
        !Array.isArray(value.volumes) || !Object.hasOwn(spaces,value.space_status)) throw new Error('FLUX 預檢資料格式無效。')
    if (current === ticket) plan.value = value
  } catch (e) { if (current === ticket && !abort.signal.aborted) error.value = e instanceof Error ? e.message : '預檢失敗。' }
  finally { if (current === ticket) {busy.value = false; controller = null} }
}
function cancel() {++ticket; controller?.abort(); controller = null; busy.value = false}
onMounted(() => {void load()})
onDeactivated(cancel)
onBeforeUnmount(cancel)
</script>
<template>
  <section class="panel flux-plan" aria-labelledby="flux-plan-heading">
    <div class="plan-heading"><h2 id="flux-plan-heading">FLUX.1 接入準備</h2><button type="button" class="secondary" :disabled="busy" @click="load">{{busy ? '讀取中…' : '更新 FLUX 安裝預檢'}}</button></div>
    <p class="footnote">固定來源、版本與本機磁碟預檢；專用創作流程已接入，尚未提供下載或 GPU 出圖驗收。</p>
    <p v-if="error" class="notice warning" role="alert">{{error}}</p>
    <template v-if="plan">
      <p class="notice" :class="{warning:plan.space_status !== 'sufficient'}" role="status">{{spaces[plan.space_status]}} · 元件合計 {{gib(plan.total_size_bytes)}}，每個磁碟區另預留 2 GiB。</p>
      <p class="footnote">{{plan.name}} · 來源核對 {{plan.verified_at}} · 本機查詢 {{new Date(plan.checked_at).toLocaleString()}}</p>
      <p><a :href="plan.source_url" target="_blank" rel="noopener">作者模型卡</a> · <a :href="plan.reference_url" target="_blank" rel="noopener">ComfyUI 整合範例</a> · <a :href="plan.license.url" target="_blank" rel="noopener">{{plan.license.name}}</a></p>
      <p class="footnote">{{plan.license.note}}</p>
      <div class="table-scroll"><table><caption>選定元件與來源版本（本機檔案尚未驗證）</caption><thead><tr><th scope="col">元件</th><th scope="col">固定版本</th><th scope="col">大小</th><th scope="col">本機狀態</th></tr></thead><tbody>
        <tr v-for="item in plan.components" :key="item.role"><th scope="row"><a :href="item.source_url" target="_blank" rel="noopener">{{item.name}}</a><small>{{item.filename}}</small></th><td>{{item.version}}</td><td>{{gib(item.size_bytes)}}</td><td>{{states[item.state] || '未知'}}</td></tr>
      </tbody></table></div>
      <p v-for="volume in plan.volumes" :key="volume.id" class="footnote">{{volume.path}}：可用 {{gib(volume.free_bytes)}}／完整元件與預留預算 {{gib(volume.required_bytes)}}；同一磁碟區只預留一次。</p>
      <details><summary>元件識別、精度與取得條件</summary><article v-for="item in plan.components" :key="item.role"><h3>{{item.name}}</h3><p class="footnote">{{item.provenance}} · {{item.precision}}</p><p class="footnote">{{item.license_name}}</p><p class="footnote">{{item.access === 'hf_gated_user_review' ? '來源需要 Hugging Face 帳號及使用條件確認，需使用者自行處理。' : '核對當時可公開取得，之後仍需確認來源狀態。'}}</p><dl><dt>固定修訂</dt><dd>{{item.revision}}</dd><dt>預期 SHA256</dt><dd>{{item.sha256}}</dd><dt>本機位置</dt><dd>{{item.target}}</dd></dl><p v-if="item.actual_size_bytes != null" class="footnote">本機檔案大小：{{gib(item.actual_size_bytes)}}；未驗證 hash。</p><p v-if="item.error" class="footnote">{{item.error}}</p></article></details>
      <p class="footnote">最低 VRAM／RAM：未知，需專用工作流程實測。未驗證 RTX 3060／4080，不以顯卡型號限制平台功能。</p>
      <ul class="footnote"><li v-for="warning in plan.warnings" :key="warning">{{warning}}</li></ul>
    </template>
  </section>
</template>
<style scoped>
.flux-plan{margin-top:28px;min-width:0}.plan-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.plan-heading h2{font-size:20px}.flux-plan a{color:var(--focus-ring)}.table-scroll{overflow:auto;margin:20px 0}table{border-collapse:collapse;width:100%;text-align:left;font-size:12px}caption{text-align:left;color:var(--text-muted);padding-bottom:12px}th,td{border-bottom:1px solid var(--border-control);padding:12px;vertical-align:top}th{font-weight:500}small{display:block;margin-top:8px;color:var(--text-muted);overflow-wrap:anywhere}.flux-plan details{margin-top:20px}.flux-plan summary{cursor:pointer}.flux-plan article{border-top:1px solid var(--border-control);padding:16px 0}.flux-plan h3{font-size:13px}.flux-plan dl{font-size:11px}.flux-plan dd{margin:6px 0 12px;overflow-wrap:anywhere;font-family:monospace}.flux-plan p,.flux-plan li{line-height:1.8;overflow-wrap:anywhere}
</style>
