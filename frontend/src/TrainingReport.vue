<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { apiResponse } from './apiClient'
import { createRequestScope } from './requestScope'

const props = defineProps<{ runs: { run_id: string; status: string }[]; currentId: string }>()
const selected = ref(''),
  includeLogs = ref(false),
  busy = ref(false),
  preview = ref(''),
  error = ref('')
const captured = ref(''),
  issueCount = ref(0)
const scope = createRequestScope()
let url = '',
  alive = true
function clear() {
  scope.cancel()
  busy.value = false
  preview.value = ''
  captured.value = ''
  error.value = ''
  if (url) URL.revokeObjectURL(url)
  url = ''
}
watch(
  () => props.currentId,
  (id) => {
    if (id) selected.value = id
  },
  { immediate: true },
)
watch(
  () => props.runs,
  (rows) => {
    if (!selected.value && rows.length) selected.value = rows[0]!.run_id
  },
  { immediate: true },
)
watch([selected, includeLogs], clear)
async function inspect() {
  if (!selected.value || busy.value) return
  clear()
  const request = scope.begin(),
    id = selected.value,
    logs = includeLogs.value
  busy.value = true
  try {
    const response = await apiResponse(`training/runs/${id}/report?include_logs=${logs}`, {
      signal: request.signal,
    })
    if (!response.headers.get('content-type')?.startsWith('application/json'))
      throw Error('報告回應格式不符。')
    const reader = response.body?.getReader()
    if (!reader) throw Error('報告回應不完整。')
    const chunks: Uint8Array[] = []
    let size = 0
    try {
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        size += value.byteLength
        if (size > 1024 * 1024) {
          await reader.cancel()
          throw Error('訓練報告超過 1 MiB。')
        }
        chunks.push(value)
      }
    } finally {
      reader.releaseLock()
    }
    const buffer = new ArrayBuffer(size),
      raw = new Uint8Array(buffer)
    let offset = 0
    for (const chunk of chunks) {
      raw.set(chunk, offset)
      offset += chunk.byteLength
    }
    const text = new TextDecoder('utf-8', { fatal: true }).decode(raw)
    const report = JSON.parse(text)
    if (
      report.schema_version !== 1 ||
      report.kind !== 'model-atelier-training-report' ||
      report.run_id !== id ||
      report.scope?.logs_included !== logs ||
      !Array.isArray(report.issues)
    )
      throw Error('報告識別或資料範圍不符，未提供下載。')
    if (alive && request.isCurrent()) {
      preview.value = text
      captured.value = report.capture_finished_at
      issueCount.value = report.issues.length
      url = URL.createObjectURL(new Blob([buffer], { type: 'application/json;charset=utf-8' }))
    }
  } catch (e) {
    if (alive && request.isCurrent()) error.value = String(e)
  } finally {
    if (alive && request.isCurrent()) busy.value = false
  }
}
function download() {
  if (!url || !preview.value) return
  const link = document.createElement('a')
  link.href = url
  link.download = `training-report-${selected.value}.json`
  link.click()
}
onUnmounted(() => {
  alive = false
  clear()
  scope.dispose()
})
</script>

<template>
  <section class="training-report" aria-labelledby="training-report-title">
    <h3 id="training-report-title">訓練紀錄與診斷報告</h3>
    <p
      >保存原 run 的設定、來源
      hash、狀態、資源與產物回執。只讀取紀錄，不開始／停止訓練或連接引擎；這是分次讀取的觀察，不是完整備份或權重驗證。</p
    >
    <label
      >報告 run<select v-model="selected" aria-label="報告 run"
        ><option value="">請選擇已登記 run</option
        ><option v-for="item in runs" :key="item.run_id" :value="item.run_id"
          >{{ item.run_id }} · {{ item.status }}</option
        ></select
      ></label
    >
    <p class="footnote"
      >預設不含圖片、caption、本機路徑、GPU UUID、完整 study 或日誌。資源最多保留最近 100
      筆取樣、最近 100 份 checkpoint
      回執；缺失／損壞與省略數保留在報告，未知狀態不判為已釋放。分享前先閱讀預覽。</p
    >
    <label class="log-choice"
      ><input v-model="includeLogs" type="checkbox" />附上 worker 日誌尾段與狀態訊息</label
    >
    <p v-if="includeLogs" class="notice warning"
      >日誌最後 64 KiB
      與狀態訊息可能包含本機路徑及使用者文字，未自動去識別；選擇變更後須重新預覽。</p
    >
    <button class="secondary" type="button" :disabled="!selected || busy" @click="inspect">{{
      busy ? '讀取報告中…' : '預覽訓練報告'
    }}</button>
    <p v-if="error" role="alert" class="notice warning">{{ error }}</p>
    <template v-if="preview"
      ><p role="status">報告快照：{{ captured }} · 紀錄問題 {{ issueCount }} 項</p
      ><p class="footnote"
        >下載保存本次預覽的相同 bytes，不會重新查詢。活動 run
        可能繼續更新，需明確重新預覽才取得新快照。</p
      ><pre tabindex="0" role="region" aria-label="訓練報告 JSON 預覽">{{ preview }}</pre
      ><button class="primary" type="button" @click="download"
        >下載此訓練報告 JSON</button
      ></template
    >
  </section>
</template>

<style scoped>
.training-report {
  min-width: 0;
  margin: 20px 0;
  border-top: 1px solid var(--line, #36413b);
  padding-top: 20px;
}
label {
  display: grid;
  gap: 8px;
  margin: 16px 0;
  font-size: 12px;
}
select {
  min-width: 0;
  width: 100%;
}
.log-choice {
  display: flex;
  align-items: center;
}
.log-choice input {
  width: auto;
  flex: 0 0 auto;
}
p {
  overflow-wrap: anywhere;
}
pre {
  max-height: 440px;
  max-width: 100%;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 11px;
  padding: 16px;
  background: #101517;
  color: #d7e7cf;
  border: 1px solid #3a4440;
  border-radius: 8px;
}
</style>
