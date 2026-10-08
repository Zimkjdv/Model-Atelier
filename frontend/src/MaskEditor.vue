<script setup lang="ts">
import { nextTick, onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import type { ReferenceAsset } from './referenceSettings'
import { binaryMask, maskPoint, uploadMaskAsset } from './inpaintSettings'
const props=defineProps<{ source?:ReferenceAsset; mask?:ReferenceAsset; disabled?:boolean }>()
const emit=defineEmits<{ saved:[value:ReferenceAsset]; dirty:[value:boolean]; busy:[value:boolean] }>()
const canvas=ref<HTMLCanvasElement|null>(null),ready=ref(false),dirty=ref(false),busy=ref(false),error=ref(''),message=ref('')
const brush=ref(40),erase=ref(false),white=ref(0),file=ref<HTMLInputElement|null>(null)
let ticket=0,pointer:number|null=null,last:{x:number;y:number}|null=null
watch(dirty,v=>emit('dirty',v),{flush:'sync',immediate:true});watch(busy,v=>emit('busy',v),{flush:'sync',immediate:true})
function image(url:string):Promise<HTMLImageElement> { return new Promise((resolve,reject)=>{const item=new Image();item.onload=()=>resolve(item);item.onerror=()=>reject(new Error('無法讀取素材圖片。'));item.src=url}) }
function context() {const value=canvas.value?.getContext('2d',{willReadFrequently:true});if(!value) throw new Error('此瀏覽器無法使用遮罩畫布。');return value}
function count() {const value=context().getImageData(0,0,canvas.value!.width,canvas.value!.height);white.value=binaryMask(value.data);context().putImageData(value,0,0)}
async function load() {
  const current=++ticket,source=props.source,mask=props.mask
  ready.value=false;dirty.value=false;error.value='';message.value='';pointer=null;last=null
  if(!source || source.archived) return
  await nextTick()
  if(current!==ticket || !canvas.value) return
  if(source.width*source.height>16000000) {error.value='原圖超過畫布上限。';return}
  canvas.value.width=source.width;canvas.value.height=source.height
  try {
    const ctx=context();ctx.fillStyle='black';ctx.fillRect(0,0,source.width,source.height)
    if(mask && !mask.archived && mask.width===source.width && mask.height===source.height) {
      const loaded=await image('/api/assets/'+mask.id+'/image')
      if(current!==ticket) return
      if(loaded.naturalWidth!==source.width || loaded.naturalHeight!==source.height) throw new Error('遮罩圖片實際尺寸不同，未載入。')
      ctx.fillStyle='white';ctx.fillRect(0,0,source.width,source.height);ctx.drawImage(loaded,0,0);count()
    } else white.value=0
    if(current===ticket) ready.value=true
  } catch(e) {if(current===ticket) error.value=e instanceof Error?e.message:'遮罩讀取失敗'}
}
function point(event:PointerEvent) {return maskPoint(event.clientX,event.clientY,canvas.value!.getBoundingClientRect(),canvas.value!.width,canvas.value!.height)}
function line(from:{x:number;y:number},to:{x:number;y:number}) {
  const ctx=context();ctx.strokeStyle=erase.value?'black':'white';ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=brush.value;ctx.lineCap='round';ctx.lineJoin='round'
  ctx.beginPath();ctx.moveTo(from.x,from.y);ctx.lineTo(to.x,to.y);ctx.stroke();ctx.beginPath();ctx.arc(to.x,to.y,brush.value/2,0,Math.PI*2);ctx.fill();dirty.value=true
}
function start(event:PointerEvent) {if(!ready.value || props.disabled || busy.value || pointer!==null || event.button!==0) return;pointer=event.pointerId;last=point(event);canvas.value!.setPointerCapture(pointer);line(last,last)}
function move(event:PointerEvent) {if(event.pointerId!==pointer || !last) return;const next=point(event);line(last,next);last=next}
function stop(event?:PointerEvent) {if(event && event.pointerId!==pointer) return;const captured=pointer;pointer=null;last=null;if(captured!==null && canvas.value?.hasPointerCapture(captured)) canvas.value.releasePointerCapture(captured);if(ready.value) count()}
function clear() {if(!ready.value || busy.value || props.disabled) return;const ctx=context();ctx.fillStyle='black';ctx.fillRect(0,0,canvas.value!.width,canvas.value!.height);dirty.value=true;white.value=0}
function invert() {if(!ready.value || busy.value || props.disabled) return;const ctx=context(),pixels=ctx.getImageData(0,0,canvas.value!.width,canvas.value!.height);white.value=binaryMask(pixels.data,true);ctx.putImageData(pixels,0,0);dirty.value=true}
async function upload(blob:Blob,name:string,current:number,sourceId:string) {
  const value=await uploadMaskAsset(blob,name)
  if(value.width!==props.source?.width || value.height!==props.source?.height) throw new Error('保存後的遮罩尺寸不同，未套用。')
  if(current!==ticket || props.source?.id!==sourceId) return
  emit('saved',value as ReferenceAsset);message.value='遮罩已保存為素材；請確認參數後生成。';dirty.value=false
}
async function save() {
  if(!ready.value || busy.value || props.disabled || !props.source) return
  stop();if(!white.value) {error.value='請先畫出白色編輯範圍。';return}
  const current=ticket,sourceId=props.source.id;busy.value=true;error.value=''
  try {
    const blob=await new Promise<Blob>((resolve,reject)=>canvas.value!.toBlob(v=>v?resolve(v):reject(new Error('無法輸出遮罩')),'image/png'))
    if(current===ticket) await upload(blob,'mask-'+sourceId+'.png',current,sourceId)
  } catch(e) {if(current===ticket) error.value=e instanceof Error?e.message:'保存失敗'}
  finally {busy.value=false}
}
async function selectFile(event:Event) {
  const input=event.target as HTMLInputElement,chosen=input.files?.[0];input.value=''
  if(!chosen || !props.source || props.disabled || busy.value) return
  const current=ticket,source=props.source;busy.value=true;error.value=''
  let url=''
  try {
    if(chosen.size>20*1024*1024) throw new Error('遮罩檔案不可超過 20 MiB。')
    url=URL.createObjectURL(chosen);const loaded=await image(url)
    if(current!==ticket) return
    if(loaded.naturalWidth!==source.width || loaded.naturalHeight!==source.height) throw new Error('遮罩須與原圖尺寸完全相同。')
    const ctx=context();ctx.fillStyle='white';ctx.fillRect(0,0,source.width,source.height);ctx.drawImage(loaded,0,0);dirty.value=true;count();message.value='遮罩已載入畫布，請保存後再生成。'
  } catch(e) {if(current===ticket) error.value=e instanceof Error?e.message:'載入失敗'}
  finally {if(url) URL.revokeObjectURL(url);busy.value=false}
}
watch(()=>[props.source?.id,props.mask?.id],()=>void load(),{immediate:true,flush:'post'})
onDeactivated(()=>{stop();++ticket});onBeforeUnmount(()=>{++ticket;pointer=null})
onActivated(()=>{if(!ready.value && !dirty.value) void load()})
</script>
<template>
  <section class="mask-editor" aria-label="遮罩繪製">
    <h3>標出要修改的範圍</h3>
    <p class="footnote">白色範圍會重新生成，黑色保留處理後原圖。筆刷尺寸以原圖像素計算；保存後才能使用新遮罩。</p>
    <div class="tools"><button type="button" class="secondary" :aria-pressed="!erase" :disabled="disabled || busy || !ready" @click="erase=false">筆刷</button><button type="button" class="secondary" :aria-pressed="erase" :disabled="disabled || busy || !ready" @click="erase=true">擦除</button><label for="mask-brush">大小 <input id="mask-brush" v-model.number="brush" type="range" min="1" max="256" :disabled="disabled || busy"> {{brush}} px</label></div>
    <div v-if="source && !source.archived" class="mask-stage" :style="{aspectRatio:String(source.width/source.height)}"><img :src="'/api/assets/'+source.id+'/image'" alt="遮罩繪製用原圖"><canvas ref="canvas" aria-label="在原圖上繪製白色編輯範圍" @pointerdown="start" @pointermove="move" @pointerup="stop" @pointercancel="stop" @lostpointercapture="stop" /></div>
    <div class="tools"><button type="button" class="secondary" :disabled="disabled || busy || !ready" @click="clear">清空</button><button type="button" class="secondary" :disabled="disabled || busy || !ready" @click="invert">反相</button><button type="button" class="secondary" :disabled="disabled || busy || !ready" @click="file?.click()">載入 PNG 遮罩</button><input ref="file" class="mask-file" type="file" accept="image/png" @change="selectFile"><button type="button" class="primary" :disabled="disabled || busy || !ready || !white || !dirty" @click="save">{{busy?'處理中…':'保存遮罩'}}</button></div>
    <p class="footnote" role="status">{{dirty?'遮罩尚未保存，生成已暫停。':'使用已保存遮罩。'}} 已標記 {{white.toLocaleString()}} 個原圖像素。</p>
    <p v-if="error" class="notice warning" role="alert">{{error}}</p><p v-if="message" class="notice" role="status">{{message}}</p>
  </section>
</template>
<style scoped>
.mask-editor{margin-top:20px;border-top:1px solid var(--border-control);padding-top:18px}.mask-editor h3{font-size:14px}.tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:14px 0}.tools label{display:flex;align-items:center;gap:8px;font-size:12px}.tools input{width:120px}.mask-stage{position:relative;width:100%;max-height:none;background:white;isolation:isolate}.mask-stage img{display:block;width:100%;height:100%;position:absolute;inset:0;object-fit:fill}.mask-stage canvas{display:block;position:absolute;inset:0;width:100%;height:100%;opacity:.55;mix-blend-mode:screen;touch-action:none;cursor:crosshair}.mask-file{display:none}.footnote{line-height:1.7}.tools [aria-pressed=true]{border-color:var(--focus-ring)}
</style>
