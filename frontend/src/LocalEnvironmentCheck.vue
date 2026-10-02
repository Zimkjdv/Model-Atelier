<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import EnvironmentDevices from './EnvironmentDevices.vue'
import { cudaStatus, environmentText, environmentTime } from './environmentTypes'
import type { LocalEnvironment } from './environmentTypes'
const report = ref<LocalEnvironment | null>(null), busy = ref(false), error = ref('')
let alive = true, requestToken = 0, controller: AbortController | null = null
const statusLabel = computed(() => !report.value || report.value.status === 'not_checked' ? '尚未檢查'
  : report.value.status === 'available' ? '檢查完成' : report.value.status === 'timeout' ? '檢查逾時' : '環境不可用')
async function read(run = false) {
  if (busy.value) return
  const token = ++requestToken
  controller?.abort(); controller = new AbortController()
  busy.value = true; error.value = ''
  try {
    const response = await fetch('/api/local-environment', { method: run ? 'POST' : 'GET', signal: controller.signal })
    const data = await response.json().catch(() => null)
    if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : '無法更新本機安裝檢查，原有檢查紀錄已保留。')
    if (!data || data.scope !== 'managed_local_comfyui' || !['not_checked', 'available', 'unavailable', 'timeout'].includes(data.status))
      throw new Error('本機檢查回覆格式不正確，原有紀錄已保留。')
    if (alive && token === requestToken) report.value = data as LocalEnvironment
  } catch (e) {
    if (alive && token === requestToken) error.value = e instanceof Error ? e.message : '無法取得本機安裝檢查。'
  } finally { if (alive && token === requestToken) { busy.value = false; controller = null } }
}
onMounted(() => { void read() })
onBeforeUnmount(() => { alive = false; ++requestToken; controller?.abort() })
</script>

<template>
  <article class="panel local-environment">
    <div class="panel-heading"><div><h2>本機 ComfyUI 安裝檢查</h2><p class="muted">來源：本專案 ComfyUI Python；驅動資訊另由本機 nvidia-smi 回報。</p></div><span class="status" :class="{ connected: report?.status === 'available' }">{{ statusLabel }}</span></div>
    <p class="footnote">範圍固定為本專案 runtime/ComfyUI 的 Python 環境，與目前選定的本機或遠端引擎分開。</p>
    <p v-if="report?.python_path" class="python-path">{{ report.python_path }}</p>
    <div class="local-check-actions"><button type="button" class="primary" :disabled="busy" @click="read(true)">{{ busy ? '讀取中…' : '檢查本機 ComfyUI 安裝' }}</button><span>上次檢查：{{ environmentTime(report?.checked_at) }}</span></div>
    <p class="footnote">顯示上次檢查的快照，只有按下按鈕才更新。環境變更後快照可能已過期；平台重啟後需重新檢查。</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <dl class="local-versions">
      <div><dt>本機 ComfyUI Python</dt><dd>{{ environmentText(report?.system.python) }}</dd></div>
      <div><dt>本機 PyTorch</dt><dd>{{ environmentText(report?.system.pytorch) }}</dd></div>
      <div><dt>PyTorch CUDA 建置版本</dt><dd>{{ environmentText(report?.system.cuda_runtime) }}</dd></div>
      <div><dt>CUDA 可用（本機檢查）</dt><dd :class="{ unavailable: report?.system.cuda_available === false }">{{ cudaStatus(report?.system.cuda_available) }}</dd></div>
      <div><dt>本機 NVIDIA 驅動</dt><dd>{{ environmentText(report?.system.driver) }}</dd></div>
    </dl>
    <EnvironmentDevices v-if="report?.devices.length" :devices="report.devices" memory-label="本機檢查回報 VRAM"/>
    <p v-if="report?.system.cuda_available === false" class="local-warning" role="status">此 Python 環境回報 CUDA 不可用，請依下方資訊檢查安裝與驅動。</p>
    <ul v-if="report?.warnings.length" class="local-warnings"><li v-for="(warning, index) in report.warnings" :key="index">{{ warning }}</li></ul>
    <p class="footnote">CUDA 建置版本來自 PyTorch，不代表本機 CUDA Toolkit 版本或完整驅動相容性驗證。環境檢查不會生成圖片，結果也不代表所有模型與工作流程皆可執行。</p>
  </article>
</template>

<style scoped>
.local-environment{background:linear-gradient(110deg,#202c25,#191d20)}.local-environment .panel-heading{align-items:start;gap:18px}.python-path{font-family:monospace;font-size:11px;overflow-wrap:anywhere;color:#aec3a6}.local-check-actions{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:20px 0}.local-check-actions span{font-size:10px;color:#a2b1a5}.local-versions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:22px 0}.local-versions>div{min-width:0}.local-versions dt{font-size:10px;color:#8e9e96}.local-versions dd{font-size:12px;overflow-wrap:anywhere;margin:8px 0 0}.local-versions .unavailable,.local-warning{color:#ebc4a1}.local-warning{font-size:12px}.local-warnings{font-size:11px;line-height:1.8;color:#b7aa94;padding-left:20px}@media(max-width:850px){.local-versions{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:500px){.local-versions{grid-template-columns:1fr}.local-environment .panel-heading{flex-direction:column}}
</style>
