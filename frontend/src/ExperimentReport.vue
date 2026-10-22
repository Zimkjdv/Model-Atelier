<script setup lang="ts">
import { computed,onActivated,onBeforeUnmount,onDeactivated,ref,watch } from 'vue'
import type { SavedExperiment } from './experimentSettings'
import { checkedExperimentReport } from './experimentReport'
const props=defineProps<{record:SavedExperiment}>()
const url=ref(''),error=ref(''),busy=ref(false)
const identity=computed(()=>props.record.id+':'+props.record.plan.plan_sha256)
let ticket=0,controller:AbortController|null=null,active=true
function reset() {++ticket;controller?.abort();busy.value=false;error.value='';if(url.value) URL.revokeObjectURL(url.value);url.value=''}
async function prepare() {
  if(!active || busy.value) return
  reset();const current=++ticket,key=identity.value,record=JSON.parse(JSON.stringify(props.record)),abort=new AbortController();controller=abort;busy.value=true
  try {
    const response=await fetch('/api/experiments/plans/'+record.id+'/report?'+new URLSearchParams({expected_plan_sha256:record.plan.plan_sha256}),{signal:abort.signal})
    const blob=await checkedExperimentReport(response,record)
    if(current===ticket && active && key===identity.value) url.value=URL.createObjectURL(blob)
  } catch(e) {if(current===ticket && !abort.signal.aborted) error.value=e instanceof Error?e.message:'報告準備失敗。'}
  finally {if(current===ticket) busy.value=false}
}
watch(identity,reset,{flush:'sync'});onDeactivated(()=>{active=false;reset()});onActivated(()=>{active=true});onBeforeUnmount(()=>{active=false;reset()})
</script>
<template>
  <section class="result-report" aria-label="比較結果報告">
    <button type="button" class="secondary" :disabled="busy" @click="prepare">{{busy?'準備報告中…':'準備比較結果報告'}}</button>
    <p>只匯出平台已保存的方案、原任務流程／版本／資源快照與作品 hash／人工評分，不連線引擎或生成。最多 100 筆任務與作品、8 MiB；超出時明確拒絕，不省略紀錄。</p>
    <p v-if="error" class="notice warning" role="alert">{{error}}</p>
    <a v-if="url" :href="url" :download="'comparison-results-'+record.id+'.json'">下載本次比較結果報告 JSON</a>
    <p v-if="url" role="status">這是準備當下的報告，之後的任務／評分變更不會自動更新；需要時重新準備。報告不含原圖，也不能當作可匯入的比較方案。</p>
  </section>
</template>
<style scoped>.result-report{margin:14px 0;padding:12px;border:1px solid var(--border-control);border-radius:8px;font-size:12px;overflow-wrap:anywhere}.result-report p{line-height:1.7}.result-report a{color:var(--text-notice)}</style>
