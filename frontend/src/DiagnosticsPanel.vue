<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { apiJson } from './apiClient'
type Readiness = { checked_at: string; service: { status: string }; data: { status: string }; engine: { status: string; checked_at: string | null } }
const status = ref<Readiness | null>(null), busy = ref(false), error = ref(''), jobId = ref(''), requestId = ref(''), preview = ref('')
watch([jobId, requestId], () => { preview.value = '' })
const labels: Record<string, string> = { alive: '存活', readable: '可讀', unavailable: '無法讀取', unknown: '未知／尚未檢查', connected: '已連線', offline: '離線', invalid: '回應無效' }
let alive = true, downloadUrl = ''
async function check(probe = false) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    const value = await apiJson<Readiness>('status' + (probe ? '?probe_engine=true' : ''))
    if (alive) status.value = value
  } catch (e) { if (alive) error.value = e instanceof Error ? e.message : '狀態讀取失敗' }
  finally { if (alive) busy.value = false }
}
async function inspect() {
  if (busy.value) return
  busy.value = true; error.value = ''; preview.value = ''
  try {
    const query = new URLSearchParams()
    if (jobId.value.trim()) query.set('job_id', jobId.value.trim())
    if (requestId.value.trim()) query.set('request_id', requestId.value.trim())
    const result = await apiJson<{ readiness: Readiness }>('diagnostics?' + query)
    const text = JSON.stringify(result, null, 2)
    if (new Blob([text]).size > 512 * 1024) throw new Error('診斷超過 512 KiB，請指定單一任務 UUID。')
    if (alive) { preview.value = text; status.value = result.readiness }
  } catch (e) { if (alive) error.value = e instanceof Error ? e.message : '診斷讀取失敗' }
  finally { if (alive) busy.value = false }
}
function download() {
  if (!preview.value) return
  if (downloadUrl) URL.revokeObjectURL(downloadUrl)
  downloadUrl = URL.createObjectURL(new Blob([preview.value], { type: 'application/json;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = downloadUrl; link.download = 'model-atelier-diagnostics.json'; link.click()
}
onMounted(() => { void check() })
onUnmounted(() => { alive = false; if (downloadUrl) URL.revokeObjectURL(downloadUrl) })
</script>
<template>
  <section class="panel diagnostics" aria-labelledby="diagnostics-title">
    <h2 id="diagnostics-title">故障診斷</h2>
    <p>分開確認平台、資料與引擎。引擎離線時，已保存作品仍可讀取；資料可讀不代表可寫入或所有圖片完整。</p>
    <dl v-if="status" aria-label="服務與資料狀態">
      <dt>平台服務</dt><dd>{{ labels[status.service.status] || '未知' }}</dd>
      <dt>本機資料</dt><dd>{{ labels[status.data.status] || '未知' }}（未測寫入／全檔健全性）</dd>
      <dt>引擎連線</dt><dd>{{ labels[status.engine.status] || '未知' }}<small> · {{ status.engine.checked_at ? new Date(status.engine.checked_at).toLocaleString() : '按下唯讀檢查取得狀態' }}</small></dd>
    </dl>
    <p v-if="status" class="footnote">平台／資料檢查時間：{{ new Date(status.checked_at).toLocaleString() }}。引擎結果 60 秒後視為未知，重新檢查才能取得新觀察。</p>
    <button class="secondary" :disabled="busy" @click="check(true)">唯讀檢查狀態</button>
    <p class="footnote">限本次平台程序，最多 500 筆、256 KiB、24 小時，重啟清空。預設不含提示詞、圖片、完整 workflow、憑證或個人路徑；UUID 可用於關聯同一任務。預覽不查詢任務歷史、不重新生成，也不自動分享。</p>
    <form @submit.prevent="inspect">
      <label for="diagnostic-job">任務 UUID（選填，留空顯示全部）</label>
      <input id="diagnostic-job" v-model="jobId" :disabled="busy" maxlength="36" autocomplete="off" placeholder="從生成任務複製完整 UUID">
      <label for="diagnostic-request">平台請求 ID（選填；與任務條件同時套用）</label>
      <input id="diagnostic-request" v-model="requestId" :disabled="busy" maxlength="36" autocomplete="off" placeholder="錯誤提示或 X-Request-ID 中的 UUID">
      <button class="secondary" :disabled="busy">{{ busy ? '讀取中…' : '預覽診斷 JSON' }}</button>
    </form>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <template v-if="preview"><p class="footnote">以下是本次預覽快照；下載會保存完全相同內容，請先確認再自行分享。</p><pre tabindex="0" role="region" aria-label="診斷 JSON 預覽">{{ preview }}</pre><button class="primary" @click="download">下載此預覽 JSON</button></template>
  </section>
</template>
<style scoped>
.diagnostics{max-width:900px}.diagnostics dl{display:grid;grid-template-columns:100px 1fr;gap:12px;font-size:12px}.diagnostics dd{margin:0;overflow-wrap:anywhere}.diagnostics label{display:block;margin:16px 0 8px;font-size:12px}.diagnostics input{margin-bottom:12px}.diagnostics pre{overflow:auto;max-height:380px;max-width:100%;font-size:11px;padding:16px;background:#101517;color:#d7e7cf;border:1px solid #3a4440;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere}.diagnostics button{margin:8px 8px 8px 0}@media(max-width:700px){.diagnostics dl{grid-template-columns:1fr;gap:8px}.diagnostics dd{margin-bottom:8px}}
</style>
