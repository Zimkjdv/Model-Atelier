<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import GenerationPanel from './GenerationPanel.vue'
import MaskEditor from './MaskEditor.vue'
import LoraControls from './LoraControls.vue'
import ReferenceSnapshot from './ReferenceSnapshot.vue'
import RuntimeSnapshot from './RuntimeSnapshot.vue'
import { type ReferenceAsset, type ReferenceSnapshot as ReferenceMetadata } from './referenceSettings'
import type { RuntimeMetadata } from './runtimeMetadata'
import { chooseMask, chooseSource, copyInpaint, inpaintProblem, newInpaint, type InpaintForm } from './inpaintSettings'
import { type ModelProfile, validateProfile } from './modelProfiles'
const props=defineProps<{restoreRequest?:{artworkId:string;token:number}|null}>()
const emit=defineEmits<{models:[];assets:[];gallery:[jobId:string]}>()
type Catalog={engine_url:string;models:{name:string;listed:boolean;version?:string}[]}
type Capabilities={engine_url:string;engine_matches:boolean;available:boolean;stale:boolean;sampler_names:string[];schedulers:string[];sync_error:string|null}
type Restoration={settings:InpaintForm;warnings:string[];reference_metadata?:ReferenceMetadata[]|null;runtime_metadata?:RuntimeMetadata|null;job_id?:string;artwork_id?:string}
const form=reactive(newInpaint()),catalog=ref<Catalog|null>(null),assets=ref<ReferenceAsset[]>([]),capabilities=ref<Capabilities|null>(null),profile=ref<ModelProfile|null>(null)
const busy=ref(false),error=ref(''),message=ref(''),loraBlock=ref(''),maskDirty=ref(false),maskBusy=ref(false),generationBusy=ref(false),generationPending=ref(false)
const origin=ref<Restoration|null>(null),pendingRestore=ref<Restoration|null>(null)
const baseline=ref(JSON.stringify(form)),dirty=computed(()=>JSON.stringify(form)!==baseline.value || maskDirty.value)
const source=computed(()=>assets.value.find(a=>a.id===form.image_asset_id)),mask=computed(()=>assets.value.find(a=>a.id===form.mask_asset_id))
const masks=computed(()=>assets.value.filter(a=>!a.archived && a.id!==form.image_asset_id && a.width===source.value?.width && a.height===source.value?.height))
const locked=computed(()=>busy.value || maskBusy.value || generationBusy.value || generationPending.value || !!pendingRestore.value)
let ticket=0,restoreTicket=0,controller:AbortController|null=null,restoreController:AbortController|null=null,mounted=false,alive=true
async function api<T>(path:string,method='GET',signal?:AbortSignal):Promise<T> {
  const response=await fetch('/api/'+path,{method,signal}),value=await response.json()
  if(!response.ok) throw new Error(typeof value.detail==='string'?value.detail:'無法讀取資料，請確認引擎與設定。')
  return value
}
async function load(sync=false) {
  const current=++ticket,url=form.engine_url,name=form.checkpoint
  controller?.abort();const abort=new AbortController();controller=abort;busy.value=true;error.value='';catalog.value=null;capabilities.value=null;profile.value=null
  try {
    const results=await Promise.all([api<Catalog>('models','GET',abort.signal),api<ReferenceAsset[]>('assets','GET',abort.signal),api<Capabilities>('engine/capabilities'+(sync?'/sync':''),sync?'POST':'GET',abort.signal)])
    if(current!==ticket || !alive) return
    catalog.value=results[0];assets.value=results[1];capabilities.value=results[2]
    if(!form.engine_url) {form.engine_url=results[0].engine_url;baseline.value=JSON.stringify(form)}
    if(form.engine_url!==url && url) return
    if(name && form.checkpoint===name) {
      const value=validateProfile(await api<ModelProfile>('models/profile?'+new URLSearchParams({engine_url:form.engine_url,name}),'GET',abort.signal))
      if(current===ticket && form.checkpoint===name && form.engine_url===value.engine_url && value.name===name) profile.value=value
    }
  } catch(e) {if(current===ticket && !abort.signal.aborted) error.value=e instanceof Error?e.message:'讀取失敗'}
  finally {if(current===ticket) {busy.value=false;controller=null}}
}
watch(()=>[form.engine_url,form.checkpoint],()=>{profile.value=null;if(mounted) void load()},{flush:'sync'})
const block=computed(()=>{
  if(maskDirty.value) return '新遮罩尚未保存；請先保存或重新選擇已保存遮罩。'
  if(maskBusy.value || busy.value) return '正在更新輸入與引擎資料。'
  if(loraBlock.value) return loraBlock.value
  const input=inpaintProblem(form,source.value,mask.value);if(input) return input
  if(!form.checkpoint) return '請選擇 checkpoint。'
  if(catalog.value?.engine_url!==form.engine_url) return '原設定的引擎與目前設定不同，請連接原引擎再更新。'
  if(!catalog.value.models.some(m=>m.listed && m.name===form.checkpoint)) return '模型清單未確認此 checkpoint，請到模型庫同步。'
  if(profile.value?.engine_url!==form.engine_url || profile.value.name!==form.checkpoint || !['sd1','sdxl'].includes(profile.value.architecture)) return '需明確登記 SD 1.x 或 SDXL 架構，請確認模型庫。'
  const c=capabilities.value
  if(c?.engine_url!==form.engine_url || !c.available || !c.engine_matches || c.stale) return '需更新原引擎的取樣選項；历史快照不能用於生成。'
  if(!c.sampler_names.includes(form.sampler_name) || !c.schedulers.includes(form.scheduler)) return '目前取樣器或 scheduler 未在原引擎選項內，請手動調整。'
  return ''
})
function selectSource(id:string|null) {
  if(locked.value || form.image_asset_id===id) return
  if(maskDirty.value && !window.confirm('更換原圖會清除尚未保存的遮罩，確定更換？')) return
  chooseSource(form,id);origin.value=null
}
function selectMask(id:string|null) {
  if(locked.value) return
  if(maskDirty.value && !window.confirm('載入已保存遮罩會取代目前繪製內容，確定載入？')) return
  chooseMask(form,id)
}
function savedMask(value:ReferenceAsset) {assets.value=[value,...assets.value.filter(a=>a.id!==value.id)];chooseMask(form,value.id)}
function apply(value:Restoration) {
  if(generationBusy.value || generationPending.value || maskBusy.value) return
  const copied=copyInpaint(value.settings)
  ++restoreTicket;restoreController?.abort();Object.assign(form,copied);origin.value=value;pendingRestore.value=null;maskDirty.value=false
  baseline.value='';message.value='完整原圖、遮罩與設定已載入。請手動確認，再生成新任務。';void load()
}
async function restore(kind:'jobs'|'artworks',id:string,token?:number) {
  if(generationBusy.value || generationPending.value || maskBusy.value || !alive) {error.value='請先完成或恢復目前提交，再載入設定。';return}
  const current=++restoreTicket;restoreController?.abort();const abort=new AbortController();restoreController=abort;error.value=''
  try {
    const value=await api<Restoration>(kind+'/'+id+'/creation-settings','GET',abort.signal)
    if(current!==restoreTicket || (token!==undefined && props.restoreRequest?.token!==token) || !alive) return
    if((kind==='jobs'?value.job_id:value.artwork_id)!==id) throw new Error('回傳的來源 ID 不同，未載入。')
    copyInpaint(value.settings)
    if(dirty.value) pendingRestore.value=value;else apply(value)
  } catch(e) {if(current===restoreTicket && !abort.signal.aborted) error.value=e instanceof Error?e.message:'還原失敗'}
}
watch(()=>props.restoreRequest,value=>{if(value) void restore('artworks',value.artworkId,value.token)},{immediate:true})
onMounted(async()=>{await load();mounted=true})
onActivated(()=>{if(mounted) void load()})
onDeactivated(()=>{++ticket;controller?.abort();busy.value=false;++restoreTicket;restoreController?.abort()})
onBeforeUnmount(()=>{alive=false;++ticket;++restoreTicket;controller?.abort();restoreController?.abort()})
</script>
<template>
  <section aria-label="局部編輯工作台">
    <div class="toolbar"><strong>Checkpoint 局部編輯</strong><button class="secondary" :disabled="locked" @click="load(true)">更新清單與引擎選項</button><button class="secondary" @click="emit('assets')">管理原圖／遮罩素材 →</button><button class="secondary" @click="emit('models')">模型版本與來源 →</button></div>
    <p class="footnote">表單在工作台切換時保留；重新整理會清除未提交的表單。保存遮罩會寫入素材庫，生成後可從任務或作品載入完整原設定。目前不提供一般草稿或比較方案。</p>
    <p class="footnote">原引擎 {{form.engine_url || '讀取中'}} · 模型版本 {{catalog?.engine_url===form.engine_url ? catalog.models.find(m=>m.name===form.checkpoint)?.version || '未知':'未知'}}。一般 checkpoint 的修補品質依模型與遮罩而異。</p>
    <p v-if="error" class="notice warning" role="alert">{{error}}</p><p v-if="message" class="notice" role="status">{{message}}</p>
    <div v-if="pendingRestore" class="notice warning"><p>載入將取代目前表單及尚未保存的遮罩。</p><button class="secondary" @click="pendingRestore=null">繼續編輯</button><button class="secondary" :disabled="generationBusy || generationPending || maskBusy" @click="apply(pendingRestore)">捨棄變更並載入</button></div>
    <template v-if="origin"><p v-for="warning in origin.warnings" :key="warning" class="footnote">{{warning}}</p><ReferenceSnapshot :items="origin.reference_metadata"/><RuntimeSnapshot :item="origin.runtime_metadata"/></template>
    <div class="inpaint-grid">
      <form class="panel editor" @submit.prevent><fieldset :disabled="locked">
        <h2>原圖與生成設定</h2><label for="inpaint-title">名稱</label><input id="inpaint-title" v-model="form.title" required maxlength="100">
        <label for="inpaint-checkpoint">Checkpoint</label><select id="inpaint-checkpoint" v-model="form.checkpoint"><option value="">選擇模型</option><option v-if="form.checkpoint && !catalog?.models.some(m=>m.name===form.checkpoint)" :value="form.checkpoint">{{form.checkpoint}}（清單未確認）</option><option v-for="model in catalog?.models" :key="model.name" :value="model.name" :disabled="!model.listed">{{model.name}}{{!model.listed?'（已不在清單）':''}}</option></select>
        <label for="inpaint-source">原圖</label><select id="inpaint-source" :value="form.image_asset_id ?? ''" @change="selectSource(($event.target as HTMLSelectElement).value || null)"><option value="">選擇原圖素材</option><option v-if="form.image_asset_id && !source" :value="form.image_asset_id">原素材不存在（{{form.image_asset_id}}）</option><option v-for="asset in assets.filter(a=>!a.archived || a.id===form.image_asset_id)" :key="asset.id" :value="asset.id" :disabled="asset.archived">{{asset.title}} · {{asset.width}} × {{asset.height}}{{asset.archived?'（已封存）':''}}</option></select>
        <label for="inpaint-mask">已保存遮罩</label><select id="inpaint-mask" :value="form.mask_asset_id ?? ''" @change="selectMask(($event.target as HTMLSelectElement).value || null)"><option value="">繪製新遮罩或選擇素材</option><option v-if="form.mask_asset_id && !masks.some(m=>m.id===form.mask_asset_id)" :value="form.mask_asset_id">原遮罩目前不可用（{{form.mask_asset_id}}）</option><option v-for="asset in masks" :key="asset.id" :value="asset.id">{{asset.title}} · {{asset.width}} × {{asset.height}}</option></select>
        <MaskEditor :source="source" :mask="mask" :disabled="busy || generationBusy || generationPending || !!pendingRestore" @saved="savedMask" @dirty="maskDirty=$event" @busy="maskBusy=$event" />
        <label for="inpaint-prompt">提示詞</label><textarea id="inpaint-prompt" v-model="form.prompt" maxlength="20000" rows="5" placeholder="描述編輯範圍內的新物件、動作或場景"/>
        <label for="inpaint-negative">負面提示詞</label><textarea id="inpaint-negative" v-model="form.negative_prompt" maxlength="20000" rows="3"/>
        <div class="fields"><label for="inpaint-width">寬度<input id="inpaint-width" v-model.number="form.width" type="number" min="64" max="8192" step="8"></label><label for="inpaint-height">高度<input id="inpaint-height" v-model.number="form.height" type="number" min="64" max="8192" step="8"></label></div>
        <label for="inpaint-resize">原圖與遮罩縮放</label><select id="inpaint-resize" v-model="form.reference_resize"><option value="fit">等比縮放；原圖補白、遮罩補黑</option><option value="stretch">拉伸至輸出尺寸</option></select>
        <label for="inpaint-seed">Seed（精確整數）</label><input id="inpaint-seed" v-model="form.seed" inputmode="numeric" maxlength="20" pattern="[0-9]{1,20}">
        <div class="fields"><label for="inpaint-steps">Steps<input id="inpaint-steps" v-model.number="form.steps" type="number" min="1" max="150" step="1"></label><label for="inpaint-cfg">CFG<input id="inpaint-cfg" v-model.number="form.cfg" type="number" min="0" max="30" step="any"></label></div>
        <label for="inpaint-sampler">取樣器</label><select id="inpaint-sampler" v-model="form.sampler_name"><option v-if="!capabilities?.sampler_names.includes(form.sampler_name)" :value="form.sampler_name">{{form.sampler_name}}（未確認）</option><option v-for="name in capabilities?.sampler_names" :key="name" :value="name">{{name}}</option></select>
        <label for="inpaint-scheduler">Scheduler</label><select id="inpaint-scheduler" v-model="form.scheduler"><option v-if="!capabilities?.schedulers.includes(form.scheduler)" :value="form.scheduler">{{form.scheduler}}（未確認）</option><option v-for="name in capabilities?.schedulers" :key="name" :value="name">{{name}}</option></select>
        <div class="fields"><label for="inpaint-denoise">改動幅度<input id="inpaint-denoise" v-model.number="form.denoise" type="number" min="0" max="1" step="any"></label><label for="inpaint-grow">遮罩擴張<input id="inpaint-grow" v-model.number="form.grow_mask_by" type="number" min="0" max="64" step="1"></label></div>
        <p class="footnote">透明遮罩先合成白底，灰階 128 以上為編輯範圍。擴張供模型去噪使用；最終合成仍使用原二值遮罩。一般 checkpoint 可能需要較高 denoise，沒有通用品質預設。</p>
        <LoraControls v-model="form.loras" :engine-url="form.engine_url" :checkpoint="form.checkpoint" @blocked="loraBlock=$event" />
      </fieldset></form>
      <GenerationPanel :form="form" workflow="inpaint" :blocked-reason="block" :disabled="busy || maskBusy || !!pendingRestore" @busy="generationBusy=$event" @pending="generationPending=$event" @gallery="emit('gallery',$event)" @restore-job="restore('jobs',$event)"/>
    </div>
  </section>
</template>
<style scoped>
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:18px;font-size:12px}.inpaint-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:22px;align-items:start}.editor fieldset{border:0;margin:0;padding:0;min-width:0}.editor label{display:block;font-size:12px;margin:18px 0 8px}.editor input,.editor select,.editor textarea{width:100%;box-sizing:border-box;min-width:0}.editor select,.editor textarea{font:inherit;font-size:13px;border:1px solid var(--border-control);border-radius:7px;padding:12px;background:var(--surface-input);color:var(--text-primary)}.editor textarea{line-height:1.8;resize:vertical}.fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}.fields input{margin-top:8px}.footnote{overflow-wrap:anywhere;line-height:1.7}@media(max-width:1100px){.inpaint-grid{grid-template-columns:1fr}}@media(max-width:500px){.fields{grid-template-columns:1fr}}
</style>
