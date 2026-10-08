<script setup lang="ts">
import { onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import type { SavedExperiment, ExperimentResults } from './experimentSettings'
const props = defineProps<{record:SavedExperiment}>()
const emit = defineEmits<{gallery:[jobId:string]; archived:[value:boolean]}>()
const results = ref<ExperimentResults|null>(null), error = ref(''), busy = ref(false), readAt = ref('')
let ticket = 0, controller:AbortController|null = null
function stop() { ++ticket; controller?.abort(); controller = null; busy.value = false }
async function refresh() {
  stop(); const current = ticket, abort = new AbortController(); controller = abort; busy.value = true; error.value = ''
  const record = props.record
  try {
    const response = await fetch('/api/experiments/plans/'+record.id+'/results',{signal:abort.signal})
    const value = await response.json()
    if(!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : '結果無法讀取，保留上次資料。')
    if(value.plan_id !== record.id || value.plan_sha256 !== record.plan.plan_sha256) throw new Error('結果來源與目前方案不同，請重載方案。')
    if(current === ticket) { results.value = value; emit('archived',value.archived); readAt.value = new Date().toLocaleString() }
  } catch(e) { if(current === ticket && !abort.signal.aborted) error.value = e instanceof Error ? e.message : '結果無法讀取。' }
  finally { if(current === ticket) { busy.value = false; controller = null } }
}
watch(() => props.record.id+':'+props.record.plan.plan_sha256,() => { stop(); results.value = null; readAt.value = ''; void refresh() },{immediate:true})
onActivated(() => { if(!busy.value) void refresh() }); onDeactivated(stop); onBeforeUnmount(stop)
const labels:Record<string,string> = {validating:'確認模型中',uploading_input:'上傳圖片中',submitting:'提交中',queued:'等待生成',running:'生成中',completed:'已完成',failed:'失敗',unknown:'結果待確認',cancelling:'確認取消中',cancel_unknown:'取消結果待確認',cancelled:'已取消',stopping:'確認停止中',stop_unknown:'停止結果待確認',stopped:'已停止'}
</script>
<template>
  <section class="experiment-results" aria-label="比較方案的已保存結果"><h3>比較結果 · {{ record.plan.title }}</h3>
    <p class="footnote">讀取平台已保存的最後狀態，不查詢引擎或生成。請先在任務區更新狀態、到作品庫匯入，再重讀結果。每次手動生成的紀錄都保留。</p>
    <button type="button" class="secondary" :disabled="busy" @click="refresh">{{ busy ? '讀取中…' : '重讀已保存結果' }}</button><p v-if="readAt" class="footnote">讀取時間：{{ readAt }}{{ results?.archived ? ' · 方案已封存，仍可查看原結果' : '' }}</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }} 上次資料可能已過期。</p>
    <div v-if="results" class="result-grid"><article v-for="group in results.variants" :key="group.variant_id" class="result-group"><h4>{{ group.variant_id }} · {{ group.case_id }}</h4><p>{{ record.plan.axis }} = {{ group.value }} · Seed {{ record.plan.variants.find(v => v.id === group.variant_id)?.settings.seed }}</p><p v-if="!group.runs.length" class="footnote">尚無關聯任務；載入過設定不代表已生成。</p>
      <div v-for="run in group.runs" :key="run.id" class="run"><strong>{{ labels[run.status] || run.status }}</strong><p class="footnote">{{ new Date(run.created_at).toLocaleString() }} · 模型版本 {{ run.model_version || '未知' }}</p><p v-if="run.error" class="notice warning">{{ run.error }}</p><p v-if="run.status === 'unknown'" class="footnote">請在原任務確認狀態；不要為了確認結果重新生成。</p>
        <a :href="'/api/jobs/'+run.id" target="_blank" rel="noopener">原任務紀錄</a> · <a :href="'/api/jobs/'+run.id+'/workflow'">完整工作流程</a><button v-if="run.status === 'completed'" type="button" class="secondary" @click="emit('gallery',run.id)">{{ run.artworks.length ? '到作品庫查看' : '到作品庫匯入' }}</button><p v-if="run.status === 'completed' && !run.artworks.length" class="footnote">任務已完成，尚無可讀的關聯作品。</p>
        <div v-for="item in run.artworks" :key="item.id" class="output"><a v-if="item.image_available" :href="'/api/artworks/'+item.id+'/image'" target="_blank" rel="noopener"><img v-if="item.thumbnail_available" :src="'/api/artworks/'+item.id+'/image?thumbnail=true'" :alt="item.title" loading="lazy"><span v-else>查看已保存原圖</span></a><p v-else class="notice warning">原圖檔案遺失，來源紀錄仍保留。</p><p class="footnote">{{ item.width }} × {{ item.height }}{{ item.archived ? ' · 已封存作品' : '' }}</p></div>
      </div>
    </article></div>
  </section>
</template>
<style scoped>
.experiment-results{min-width:0;margin:18px 0;padding:14px;border:1px solid var(--border-control);border-radius:8px;overflow-wrap:anywhere}.result-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:12px}.result-group{min-width:0;padding:12px;background:var(--surface-input);border-radius:7px}.run{border-top:1px solid var(--border-control);margin-top:12px;padding-top:12px}h3{font-size:14px}h4{font-size:13px}.output img{display:block;width:100%;max-height:300px;object-fit:contain;border-radius:6px}button{margin:10px 0}p{line-height:1.7}a{color:var(--text-notice)}
</style>
