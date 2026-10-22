<script setup lang="ts">
import { computed,onActivated,onBeforeUnmount,onDeactivated,ref,watch } from 'vue'
import type { FeatherForm } from './inpaintSettings'
import { blendPreviewIdentity,checkedBlendPreview } from './inpaintPreview'
const props=defineProps<{form:FeatherForm;blocked:string;disabled:boolean}>()
const image=ref(''),error=ref(''),busy=ref(false)
const identity=computed(()=>blendPreviewIdentity(props.form))
let ticket=0,controller:AbortController|null=null,active=true
function reset() { ++ticket;controller?.abort();busy.value=false;error.value='';if(image.value) URL.revokeObjectURL(image.value);image.value='' }
async function preview() {
  if(!active || busy.value || props.disabled || props.blocked) return
  reset();const current=++ticket,key=identity.value,input=JSON.parse(JSON.stringify(props.form)),abort=new AbortController();controller=abort;busy.value=true
  try {
    const response=await fetch('/api/inpaint-feather/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input),signal:abort.signal})
    const blob=await checkedBlendPreview(response,input)
    if(current!==ticket || !active || key!==identity.value || props.blocked || props.disabled) return
    image.value=URL.createObjectURL(blob)
  } catch(e) {if(current===ticket && !abort.signal.aborted) error.value=e instanceof Error?e.message:'預覽失敗。'}
  finally {if(current===ticket) busy.value=false}
}
watch(()=>[identity.value,props.blocked,props.disabled],reset)
onDeactivated(()=>{active=false;reset()});onActivated(()=>{active=true})
onBeforeUnmount(()=>{active=false;reset()})
</script>
<template>
  <section class="blend-preview" aria-label="合成遮罩預覽">
    <h3>合成遮罩預覽</h3>
    <p>使用已保存素材，在本機 CPU 計算實際合成遮罩；不需要引擎、不建立生成任務。白色完全套用生成圖、灰色混合、黑色保留處理後原圖。</p>
    <button type="button" class="secondary" :disabled="busy || disabled || !!blocked" @click="preview">{{busy?'計算中…':'預覽合成遮罩'}}</button>
    <p v-if="blocked" class="footnote">{{blocked}}</p><p v-if="error" class="notice warning" role="alert">{{error}}</p>
    <figure v-if="image"><img :src="image" alt="本次表單已保存遮罩的內側羽化灰階預覽" @error="reset();error='預覽圖片無法解碼，請重做預覽。'"><figcaption>{{form.width}} × {{form.height}} · 內側半徑 {{form.feather_radius}} 輸出像素。修改來源、遮罩、尺寸、縮放或半徑後會清除預覽。</figcaption></figure>
    <p v-else-if="!busy" class="footnote">尚無目前設定的預覽。預覽不是生成結果，也不保證修補品質。</p>
  </section>
</template>
<style scoped>
.blend-preview{border:1px solid var(--border-control);border-radius:8px;padding:14px;margin:18px 0;font-size:12px;line-height:1.7}.blend-preview h3{font-size:13px;margin-top:0}.blend-preview figure{margin:12px 0}.blend-preview img{display:block;width:100%;max-height:300px;object-fit:contain;background:#000}.blend-preview figcaption{margin-top:8px;color:var(--text-secondary)}
</style>
