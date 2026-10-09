<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import { edgeMetadata, type ControlEdge } from './controlEdges'
const props=defineProps<{jobId:string;artworkId?:string}>()
const item=ref<ControlEdge|null>(null),error=ref(''),busy=ref(false),opened=ref(false),imageFailed=ref(false)
let revision=0,controller:AbortController|null=null,active=true
const imageUrl=computed(()=>item.value?.state==='saved' && item.value.image_available && !imageFailed.value ? '/api/jobs/'+item.value.job_id+'/control-edge/image' : '')
function invalidate() { ++revision;controller?.abort();busy.value=false }
async function load(importImage=false) {
  if (!active || busy.value || (importImage && !item.value?.import_allowed)) return
  const current=++revision,jobId=props.jobId,artworkId=props.artworkId,abort=new AbortController()
  controller?.abort();controller=abort;busy.value=true;error.value=''
  // A failed reload must not leave a previously validated picture on screen.
  if (!importImage) item.value=null
  try {
    const path=importImage ? '/api/jobs/'+jobId+'/control-edge' : artworkId ? '/api/artworks/'+artworkId+'/control-edge' : '/api/jobs/'+jobId+'/control-edge'
    const response=await fetch(path,{method:importImage?'POST':'GET',signal:abort.signal}),value=await response.json()
    if (current!==revision || !active || jobId!==props.jobId || artworkId!==props.artworkId) return
    if (!response.ok) throw new Error(typeof value.detail==='string'?value.detail:'邊緣圖讀取失敗。')
    item.value=edgeMetadata(value,jobId);imageFailed.value=false
  } catch(e) { if (current===revision && !abort.signal.aborted && active) error.value=e instanceof Error?e.message:'邊緣圖讀取失敗。' }
  finally { if(current===revision) busy.value=false }
}
function toggle(event:Event) { opened.value=(event.target as HTMLDetailsElement).open;if(opened.value && !item.value && !busy.value) void load() }
watch(()=>[props.jobId,props.artworkId],()=>{invalidate();item.value=null;error.value='';imageFailed.value=false;if(opened.value) void load()})
onDeactivated(()=>{active=false;invalidate()})
onActivated(()=>{active=true;if(opened.value) void load()})
onBeforeUnmount(()=>{active=false;invalidate()})
</script>
<template>
  <details class="control-edge" @toggle="toggle">
    <summary>查看原任務的 Canny 邊緣圖</summary>
    <p class="footnote">原任務同次執行的條件圖，不隨目前表單變動；尚未提交的設定沒有即時邊緣預覽。</p>
    <p v-if="busy" role="status">{{item ? '從原引擎保存中…' : '讀取本機紀錄中…'}}</p>
    <p v-if="error" class="notice warning" role="alert">{{error}}</p>
    <template v-if="item">
      <p role="status">{{item.message}}</p>
      <button v-if="item.state==='not_saved' && item.import_allowed" type="button" class="secondary" :disabled="busy" @click="load(true)">從原引擎保存邊緣圖</button>
      <p v-if="item.state==='not_saved'" class="footnote">此按鈕只讀取原引擎 output，不建立新生成。原輸出若已遺失，不會重新計算。</p>
      <figure v-if="imageUrl"><img :src="imageUrl" alt="此任務實際使用的黑白 Canny 邊緣圖" @error="imageFailed=true;error='本機邊緣圖片無法讀取，請更新紀錄或從備份還原。'"><figcaption>{{item.width}} × {{item.height}} · 邊緣像素 {{item.edge_pixels}} / {{item.total_pixels}}（{{((item.edge_pixels || 0)/(item.total_pixels || 1)*100).toFixed(2)}}%）</figcaption></figure>
      <p v-if="item.sha256" class="hash">PNG SHA256：{{item.sha256}}</p>
      <p v-if="item.anchor" class="hash">原流程 SHA256：{{item.anchor.workflow_sha256}}</p>
      <p v-if="item.saved_at" class="footnote">保存時間：{{new Date(item.saved_at).toLocaleString()}}。邊緣像素比例只是量測，不代表品質或符合提示詞的程度。</p>
      <a v-if="imageUrl" :href="imageUrl+'?download=true'">下載原邊緣 PNG ↓</a>
    </template>
    <button type="button" class="secondary" :disabled="busy" @click="load()">更新本機保存狀態</button>
  </details>
</template>
<style scoped>
.control-edge{margin:14px 0;padding:12px;border:1px solid var(--border-control);border-radius:8px;overflow-wrap:anywhere;font-size:12px}.control-edge summary{cursor:pointer}.control-edge p{line-height:1.7}.control-edge figure{margin:12px 0}.control-edge img{display:block;width:100%;max-height:340px;object-fit:contain;background:#000}.control-edge figcaption{margin-top:8px;line-height:1.7;color:var(--text-secondary)}.hash{font-family:monospace}.control-edge button,.control-edge a{display:inline-block;margin:8px 12px 0 0}.control-edge a{color:#c5dfba}
</style>
