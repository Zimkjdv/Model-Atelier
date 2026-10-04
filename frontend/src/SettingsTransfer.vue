<script setup lang="ts">
import { computed, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import type { CreationForm } from './creationSettings'
import type { FluxForm } from './fluxSettings'
import type { ImportPreview } from './settingsTransfer'
const props = defineProps<{ settings: CreationForm | FluxForm; family: 'checkpoint' | 'flux'; dirty: boolean; disabled?: boolean }>()
const emit = defineEmits<{ apply: [value: ImportPreview] }>()
const input = ref(''), preview = ref<ImportPreview | null>(null), error = ref(''), message = ref(''), busy = ref(false)
const exported = ref(''), exportedUrl = ref('')
let ticket = 0, controller: AbortController | null = null
const workflow = computed(() => 'workflow_id' in props.settings ? props.settings.workflow_id
  : props.settings.workflow_mode === 'image2image' ? 'checkpoint-image2image-v1' : 'checkpoint-text2image-v1')
const blocked = computed(() => props.disabled || busy.value)
function display(value: unknown) { return typeof value === 'string' ? value : JSON.stringify(value) ?? '未知' }
const rows = computed(() => preview.value ? Object.entries(preview.value.bundle.settings).map(([key, value]) => {
  const previous = (props.settings as unknown as Record<string, unknown>)[key]
  return { key, before: display(previous), after: display(value), changed: JSON.stringify(previous) !== JSON.stringify(value) }
}) : [])
function invalidate() {
  ++ticket; controller?.abort(); controller = null; busy.value = false
  if (preview.value) message.value = '文件或目前設定已變更，請重新驗證後套用。'
  preview.value = null
}
watch(input, invalidate)
watch(() => JSON.stringify(props.settings), invalidate)
onBeforeUnmount(() => { invalidate(); if (exportedUrl.value) URL.revokeObjectURL(exportedUrl.value) }); onDeactivated(invalidate)
async function readFile(event: Event) {
  const control = event.target as HTMLInputElement, file = control.files?.[0]
  if (!file) return
  invalidate(); error.value = ''; message.value = ''
  const current = ticket
  try {
    if (file.size > 256 * 1024) throw new Error('設定檔不可超過 256 KiB。')
    const text = await file.text()
    if (ticket === current) { input.value = text; message.value = `已讀取 ${file.name}，請驗證並預覽。` }
  } catch (e) { if (ticket === current) error.value = e instanceof Error ? e.message : '無法讀取設定檔。' }
  finally { control.value = '' }
}
async function request(path: string, body: string, signal: AbortSignal) {
  const response = await fetch('/api/creation-settings/' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, signal })
  const text = await response.text()
  if (!response.ok) {
    const data = JSON.parse(text)
    throw new Error(typeof data.detail === 'string' ? data.detail : '設定格式無效，原表單保持不變。')
  }
  return text
}
async function validate() {
  if (blocked.value) return
  invalidate(); const current = ticket, abort = new AbortController(); controller = abort
  busy.value = true; error.value = ''; message.value = ''
  try {
    if (new Blob([input.value]).size > 256 * 1024) throw new Error('設定檔不可超過 256 KiB。')
    const value = JSON.parse(await request('import', input.value, abort.signal)) as ImportPreview
    if (current !== ticket) return
    const isFlux = value.bundle.workflow_id === 'flux1-schnell-text2image-v1'
    if (isFlux !== (props.family === 'flux')) throw new Error(`這份文件屬於 ${isFlux ? 'FLUX' : 'checkpoint'} 流程，請先切到對應工作台再匯入。`)
    preview.value = value
    message.value = '已完成格式驗證；檢查差異後，可套用為新草稿。'
  } catch (e) { if (current === ticket && !abort.signal.aborted) error.value = e instanceof Error ? e.message : '驗證失敗。' }
  finally { if (current === ticket) { busy.value = false; controller = null } }
}
async function exportSettings() {
  if (blocked.value) return
  invalidate(); const current = ticket, abort = new AbortController(); controller = abort
  busy.value = true; error.value = ''; message.value = ''
  try {
    const text = await request('export', JSON.stringify({ workflow_id: workflow.value, settings: props.settings }), abort.signal)
    if (current !== ticket) return
    exported.value = text
    if (exportedUrl.value) URL.revokeObjectURL(exportedUrl.value)
    const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }))
    exportedUrl.value = url
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `model-atelier-${props.family}-settings.json`; anchor.click()
    message.value = '已匯出目前創作設定；未保存草稿或提交生成。'
  } catch (e) { if (current === ticket && !abort.signal.aborted) error.value = e instanceof Error ? e.message : '匯出失敗。' }
  finally { if (current === ticket) { busy.value = false; controller = null } }
}
function apply() {
  if (!preview.value || blocked.value) return
  const value = preview.value
  preview.value = null
  emit('apply', value)
  message.value = '已套用為尚未保存的新草稿；生成需再明確操作。'
}
</script>
<template>
  <details class="settings-transfer">
    <summary>創作設定匯出／匯入</summary>
    <p class="footnote">設定檔版本 1 · 最多 256 KiB。只交換參數；不包含模型權重與素材圖片。作品的「匯出創作設定」另包含原來源快照。</p>
    <button type="button" class="secondary" :disabled="blocked" @click="exportSettings">匯出目前創作設定</button>
    <label :for="family + '-settings-file'">讀取創作設定 JSON 檔</label><input :id="family + '-settings-file'" type="file" accept=".json,application/json" :disabled="blocked" @change="readFile">
    <label :for="family + '-settings-json'">或貼上設定 JSON</label><textarea :id="family + '-settings-json'" v-model="input" rows="5" :disabled="blocked" spellcheck="false" :aria-describedby="family + '-settings-help'" />
    <p :id="family + '-settings-help'" class="footnote">驗證不改表單。只有按「套用為新草稿」才取代目前欄位；舊草稿及任務保留。</p>
    <button type="button" class="secondary" :disabled="blocked || !input.trim()" @click="validate">{{ busy ? '處理中…' : '驗證並預覽設定' }}</button>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p><p v-if="message" class="notice" role="status">{{ message }}</p>
    <section v-if="preview" aria-label="匯入設定預覽">
      <h3>套用前確認</h3><p>流程 {{ preview.bundle.workflow_id }} · {{ rows.filter(row => row.changed).length }} 個欄位不同</p>
      <p v-if="dirty" class="notice warning">目前有未保存變更。套用會取代這些欄位，舊的已保存草稿仍保留。</p>
      <ul><li v-for="warning in preview.warnings" :key="warning">{{ warning }}</li></ul>
      <p v-if="preview.bundle.source_snapshot" class="footnote">文件提供的來源（未核實）：{{ preview.bundle.source_snapshot.kind }}／{{ preview.bundle.source_snapshot.id }} · 模型版本 {{ preview.bundle.source_snapshot.model_version }}</p>
      <div class="transfer-table"><table><caption>目前與文件中的完整參數</caption><thead><tr><th>欄位</th><th>目前</th><th>文件</th></tr></thead><tbody><tr v-for="row in rows" :key="row.key"><th>{{ row.key }}{{ row.changed ? '（不同）' : '' }}</th><td>{{ row.before }}</td><td>{{ row.after }}</td></tr></tbody></table></div>
      <button type="button" class="primary" :disabled="blocked" @click="apply">套用為新草稿</button>
      <button type="button" class="secondary" :disabled="blocked" @click="preview = null">取消匯入</button>
    </section>
    <a v-if="exportedUrl" :href="exportedUrl" :download="`model-atelier-${family}-settings.json`">下載上次匯出的設定</a>
    <details v-if="exported"><summary>上次匯出的設定 JSON（可能不是目前設定）</summary><pre>{{ exported }}</pre></details>
  </details>
</template>
<style scoped>
.settings-transfer{margin:20px 0;font-size:12px;min-width:0;overflow-wrap:anywhere}summary{cursor:pointer;color:var(--text-notice)}label{display:block;margin:18px 0 8px}input,textarea{width:100%;box-sizing:border-box}textarea{font:12px monospace;background:var(--surface-input);color:var(--text-primary);border:1px solid var(--border-control);border-radius:7px;padding:12px;resize:vertical}button{margin:8px 8px 0 0}ul{padding-left:18px;line-height:1.7}.transfer-table{max-height:380px;overflow:auto;border:1px solid var(--border-control);margin:14px 0}table{width:100%;border-collapse:collapse;table-layout:fixed}caption{padding:12px;text-align:left}th,td{padding:10px;border-bottom:1px solid var(--border-control);text-align:left;vertical-align:top;overflow-wrap:anywhere;white-space:pre-wrap}th{color:var(--text-notice)}pre{max-height:260px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}h3{font-size:13px}
</style>
