<script setup lang="ts">
import { computed,onActivated,onBeforeUnmount,onDeactivated,ref,watch } from 'vue'
import type { ControlForm } from './controlSettings'
import type { ReferenceAsset } from './referenceSettings'
import { cannyPreviewIdentity,cannyPreviewInput,cannyPreviewProblem,checkedCannyPreview,type CannyPreviewInfo } from './cannyPreview'
const props=defineProps<{form:ControlForm;source?:ReferenceAsset;disabled:boolean}>()
const image=ref(''),info=ref<CannyPreviewInfo|null>(null),error=ref(''),busy=ref(false)
const identity=computed(()=>cannyPreviewIdentity(props.form,props.source)),blocked=computed(()=>cannyPreviewProblem(props.form,props.source))
let ticket=0,controller:AbortController|null=null,active=true
function reset() {++ticket;controller?.abort();busy.value=false;error.value='';info.value=null;if(image.value) URL.revokeObjectURL(image.value);image.value=''}
async function preview() {
  if(!active || busy.value || props.disabled || blocked.value || !props.source) return
  reset();const current=++ticket,key=identity.value,form=JSON.parse(JSON.stringify(props.form)),source={...props.source},abort=new AbortController();controller=abort;busy.value=true
  try {
    const response=await fetch('/api/control/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cannyPreviewInput(form)),signal:abort.signal})
    const result=await checkedCannyPreview(response,form,source)
    if(current!==ticket || !active || key!==identity.value || blocked.value || props.disabled) return
    image.value=URL.createObjectURL(result.blob);info.value=result.info
  } catch(e) {if(current===ticket && !abort.signal.aborted) error.value=e instanceof Error?e.message:'預覽失敗。'}
  finally {if(current===ticket) busy.value=false}
}
watch(()=>[identity.value,blocked.value,props.disabled],reset,{flush:'sync'})
onDeactivated(()=>{active=false;reset()});onActivated(()=>{active=true})
onBeforeUnmount(()=>{active=false;reset()})
</script>
<template>
  <section class="canny-preview" aria-label="送出前 Canny 預覽">
    <h3>送出前 Canny 預覽</h3>
    <p>以目前來源、尺寸、縮放與閾值在本機 CPU 計算。無需模型或引擎，不建立生成任務。最多 1,048,576 像素，45 秒逾時會停止。</p>
    <button type="button" class="secondary" :disabled="busy || disabled || !!blocked" @click="preview">{{busy?'計算 Canny 中…':'預覽 Canny 邊緣'}}</button>
    <p v-if="busy" role="status">正在本機 CPU 計算；可繼續修改設定，過期回覆不會顯示。</p>
    <p v-if="blocked" class="footnote">{{blocked}}</p><p v-if="error" class="notice warning" role="alert">{{error}}</p>
    <figure v-if="image"><img :src="image" alt="目前未提交設定的本機 CPU Canny 二值邊緣預覽" @error="reset();error='預覽圖片無法解碼，請重做預覽。'"><figcaption>{{form.width}} × {{form.height}} · 閾值 {{form.canny_low}}／{{form.canny_high}} · {{form.reference_resize==='fit'?'等比補白':'拉伸'}}。修改來源、尺寸、縮放或閾值後會清除預覽。</figcaption></figure>
    <p v-else-if="!busy" class="footnote">尚無目前設定的預覽；按下按鈕才計算，不會自動產生圖片。</p>
    <p class="footnote">這是本機近似預覽，不是原任務輸出；不同 CPU／GPU 或引擎版本可能產生差異。原任務實際邊緣仍從完成任務另行保存。</p>
    <details v-if="info"><summary>本次 CPU 預覽來源</summary><p>{{info.method}} · float32 CPU<br>Torch {{info.torch}} · Kornia {{info.kornia}} · Pillow {{info.pillow}}</p><p>原生 Canny 原碼 SHA256：{{info.native_sha256}}</p><p>處理後輸入 SHA256：{{info.input_sha256}}</p><p>預覽 PNG SHA256：{{info.sha256}}</p></details>
  </section>
</template>
<style scoped>
.canny-preview{border:1px solid var(--border-control);border-radius:8px;padding:14px;margin:18px 0;font-size:12px;line-height:1.7;overflow-wrap:anywhere}.canny-preview h3{font-size:13px;margin-top:0}.canny-preview figure{margin:12px 0}.canny-preview img{display:block;width:100%;max-height:340px;object-fit:contain;background:#000}.canny-preview figcaption{margin-top:8px;color:var(--text-secondary)}.canny-preview summary{cursor:pointer}
</style>
