<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import GenerationPanel from './GenerationPanel.vue'
import ControlSnapshot from './ControlSnapshot.vue'
import { registeredControlProblem, type ControlCatalog, type ControlMetadata } from './controlSettings'
import LoraControls from './LoraControls.vue'
import ReferenceSnapshot from './ReferenceSnapshot.vue'
import RuntimeSnapshot from './RuntimeSnapshot.vue'
import { type ReferenceAsset, type ReferenceSnapshot as ReferenceMetadata } from './referenceSettings'
import type { RuntimeMetadata } from './runtimeMetadata'
import { chooseSource, copyControl, controlProblem, newControl, type ControlForm } from './controlSettings'
import { type ModelProfile, validateProfile } from './modelProfiles'
const props=defineProps<{restoreRequest?:{artworkId:string;token:number}|null}>()
const emit=defineEmits<{models:[];assets:[];gallery:[jobId:string]}>()
type Catalog={engine_url:string;models:{name:string;listed:boolean;version?:string}[]}
type Capabilities={engine_url:string;engine_matches:boolean;available:boolean;stale:boolean;sampler_names:string[];schedulers:string[];sync_error:string|null}
type Restoration={settings:ControlForm;component_metadata?:ControlMetadata[]|null;warnings:string[];reference_metadata?:ReferenceMetadata[]|null;runtime_metadata?:RuntimeMetadata|null;job_id?:string;artwork_id?:string}
const form=reactive(newControl()),catalog=ref<Catalog|null>(null),assets=ref<ReferenceAsset[]>([]),capabilities=ref<Capabilities|null>(null),profile=ref<ModelProfile|null>(null)
const busy=ref(false),error=ref(''),message=ref(''),loraBlock=ref(''),generationBusy=ref(false),generationPending=ref(false)
const origin=ref<Restoration|null>(null),pendingRestore=ref<Restoration|null>(null)
const baseline=ref(JSON.stringify(form)),dirty=computed(()=>JSON.stringify(form)!==baseline.value)
const controls=ref<ControlCatalog|null>(null)
const source=computed(()=>assets.value.find(a=>a.id===form.image_asset_id))
const controlModel=computed(()=>controls.value?.controlnets.find(m=>m.name===form.control_net_name))
const locked=computed(()=>busy.value || generationBusy.value || generationPending.value || !!pendingRestore.value)
let ticket=0,restoreTicket=0,controller:AbortController|null=null,restoreController:AbortController|null=null,mounted=false,alive=true
async function api<T>(path:string,method='GET',signal?:AbortSignal):Promise<T> {
  const response=await fetch('/api/'+path,{method,signal}),value=await response.json()
  if(!response.ok) throw new Error(typeof value.detail==='string'?value.detail:'無法讀取資料，請確認引擎與設定。')
  return value
}
async function load(sync=false) {
  const current=++ticket,url=form.engine_url,name=form.checkpoint
  controller?.abort();const abort=new AbortController();controller=abort;busy.value=true;error.value='';catalog.value=null;capabilities.value=null;profile.value=null;controls.value=null
  try {
    const results=await Promise.all([api<Catalog>('models','GET',abort.signal),api<ControlCatalog>('controlnets','GET',abort.signal),api<ReferenceAsset[]>('assets','GET',abort.signal),api<Capabilities>('engine/capabilities'+(sync?'/sync':''),sync?'POST':'GET',abort.signal)])
    if(current!==ticket || !alive) return
    catalog.value=results[0];controls.value=results[1];assets.value=results[2];capabilities.value=results[3]
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
  if(busy.value) return '正在更新輸入與引擎資料。'
  if(loraBlock.value) return loraBlock.value
  const input=controlProblem(form,source.value);if(input) return input
  if(!form.checkpoint) return '請選擇 checkpoint。'
  if(catalog.value?.engine_url!==form.engine_url) return '原設定的引擎與目前設定不同，請連接原引擎再更新。'
  if(!catalog.value.models.some(m=>m.listed && m.name===form.checkpoint)) return '模型清單未確認此 checkpoint，請到模型庫同步。'
  if(profile.value?.engine_url!==form.engine_url || profile.value.name!==form.checkpoint || !['sd1','sdxl'].includes(profile.value.architecture)) return '需明確登記 SD 1.x 或 SDXL 架構，請確認模型庫。'
  const control=registeredControlProblem(controls.value,form.engine_url,form.control_net_name,profile.value.architecture);if(control) return control
  const c=capabilities.value
  if(c?.engine_url!==form.engine_url || !c.available || !c.engine_matches || c.stale) return '需更新原引擎的取樣選項；历史快照不能用於生成。'
  if(!c.sampler_names.includes(form.sampler_name) || !c.schedulers.includes(form.scheduler)) return '目前取樣器或 scheduler 未在原引擎選項內，請手動調整。'
  return ''
})
function selectSource(id:string|null) { if(!locked.value) {chooseSource(form,id);origin.value=null} }
function apply(value:Restoration) {
  if(generationBusy.value || generationPending.value) return
  const copied=copyControl(value.settings)
  ++restoreTicket;restoreController?.abort();Object.assign(form,copied);origin.value=value;pendingRestore.value=null
  baseline.value='';message.value='完整結構來源、控制模型與設定已載入。請手動確認，再生成新任務。';void load()
}
async function restore(kind:'jobs'|'artworks',id:string,token?:number) {
  if(generationBusy.value || generationPending.value || !alive) {error.value='請先完成或恢復目前提交，再載入設定。';return}
  const current=++restoreTicket;restoreController?.abort();const abort=new AbortController();restoreController=abort;error.value=''
  try {
    const value=await api<Restoration>(kind+'/'+id+'/creation-settings','GET',abort.signal)
    if(current!==restoreTicket || (token!==undefined && props.restoreRequest?.token!==token) || !alive) return
    if((kind==='jobs'?value.job_id:value.artwork_id)!==id) throw new Error('回傳的來源 ID 不同，未載入。')
    copyControl(value.settings)
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
  <section aria-label="結構參考工作台">
    <div class="toolbar"><strong>Checkpoint 結構參考</strong><button class="secondary" :disabled="locked" @click="load(true)">更新清單與引擎選項</button><button class="secondary" @click="emit('assets')">管理結構素材素材 →</button><button class="secondary" @click="emit('models')">模型版本與來源 →</button></div>
    <p class="footnote">表單在工作台切換時保留；重新整理會清除未提交的表單。生成後可從任務或作品載入完整原設定。目前不提供一般草稿或比較方案。</p>
    <p class="footnote">原引擎 {{form.engine_url || '讀取中'}} · 模型版本 {{catalog?.engine_url===form.engine_url ? catalog.models.find(m=>m.name===form.checkpoint)?.version || '未知':'未知'}}。Canny 引導輪廓／構圖，不保證畫風、角色或逐像素相同。</p>
    <p v-if="error" class="notice warning" role="alert">{{error}}</p><p v-if="message" class="notice" role="status">{{message}}</p>
    <div v-if="pendingRestore" class="notice warning"><p>載入將取代目前未提交表單。</p><button class="secondary" @click="pendingRestore=null">繼續編輯</button><button class="secondary" :disabled="generationBusy || generationPending" @click="apply(pendingRestore)">捨棄變更並載入</button></div>
    <template v-if="origin"><p v-for="warning in origin.warnings" :key="warning" class="footnote">{{warning}}</p><ControlSnapshot :items="origin.component_metadata"/><ReferenceSnapshot :items="origin.reference_metadata"/><RuntimeSnapshot :item="origin.runtime_metadata"/></template>
    <div class="control-grid">
      <form class="panel editor" @submit.prevent><fieldset :disabled="locked">
        <h2>原圖與生成設定</h2><label for="control-title">名稱</label><input id="control-title" v-model="form.title" required maxlength="100">
        <label for="control-checkpoint">Checkpoint</label><select id="control-checkpoint" v-model="form.checkpoint"><option value="">選擇模型</option><option v-if="form.checkpoint && !catalog?.models.some(m=>m.name===form.checkpoint)" :value="form.checkpoint">{{form.checkpoint}}（清單未確認）</option><option v-for="model in catalog?.models" :key="model.name" :value="model.name" :disabled="!model.listed">{{model.name}}{{!model.listed?'（已不在清單）':''}}</option></select>
        <label for="control-source">原圖</label><select id="control-source" :value="form.image_asset_id ?? ''" @change="selectSource(($event.target as HTMLSelectElement).value || null)"><option value="">選擇原圖素材</option><option v-if="form.image_asset_id && !source" :value="form.image_asset_id">原素材不存在（{{form.image_asset_id}}）</option><option v-for="asset in assets.filter(a=>!a.archived || a.id===form.image_asset_id)" :key="asset.id" :value="asset.id" :disabled="asset.archived">{{asset.title}} · {{asset.width}} × {{asset.height}}{{asset.archived?'（已封存）':''}}</option></select>
        <figure v-if="source" class="source-preview"><img :src="'/api/assets/'+source.id+'/image'" :alt="'結構參考素材：'+source.title"><figcaption>原素材預覽；生成時先縮放／補白，再由原引擎計算 Canny。此處不是邊緣圖。</figcaption></figure>
        <label for="control-model">Canny ControlNet</label><select id="control-model" v-model="form.control_net_name"><option value="">選擇控制模型</option><option v-if="form.control_net_name && !controlModel" :value="form.control_net_name">{{form.control_net_name}}（清單未確認）</option><option v-for="model in controls?.controlnets" :key="model.name" :value="model.name" :disabled="!model.listed">{{model.name}} · {{model.version || '未知'}} · {{model.kind}}{{!model.listed?'（已不在清單）':''}}</option></select>
        <p class="footnote">控制模型版本 {{controlModel?.version || '未知'}} · 架構 {{controlModel?.architecture || '未知'}} · 類型 {{controlModel?.kind || '未知'}}。登記資料不是驗檔證明。</p>
        <label for="control-strength">控制強度<input id="control-strength" v-model.number="form.control_strength" type="number" min="0" max="10" step="any"></label>
        <div class="fields"><label for="control-start">作用起始<input id="control-start" v-model.number="form.control_start" type="number" min="0" max="1" step="any"></label><label for="control-end">作用結束<input id="control-end" v-model.number="form.control_end" type="number" min="0" max="1" step="any"></label></div>
        <div class="fields"><label for="control-low">Canny 低閾值<input id="control-low" v-model.number="form.canny_low" type="number" min="0.01" max="0.99" step="any"></label><label for="control-high">Canny 高閾值<input id="control-high" v-model.number="form.canny_high" type="number" min="0.01" max="0.99" step="any"></label></div>
        <p class="footnote">作用起始小於結束；低閾值小於高閾值。這是原生 Canny 浮點閾值，不是 OpenCV 的 0–255。控制強度沒有通用品質預設。</p>
        <label for="control-prompt">提示詞</label><textarea id="control-prompt" v-model="form.prompt" maxlength="20000" rows="5" placeholder="描述希望生成的物件、動作或場景"/>
        <label for="control-negative">負面提示詞</label><textarea id="control-negative" v-model="form.negative_prompt" maxlength="20000" rows="3"/>
        <div class="fields"><label for="control-width">寬度<input id="control-width" v-model.number="form.width" type="number" min="64" max="8192" step="8"></label><label for="control-height">高度<input id="control-height" v-model.number="form.height" type="number" min="64" max="8192" step="8"></label></div>
        <label for="control-resize">結構素材縮放</label><select id="control-resize" v-model="form.reference_resize"><option value="fit">等比縮放並補白</option><option value="stretch">拉伸至輸出尺寸</option></select>
        <label for="control-seed">Seed（精確整數）</label><input id="control-seed" v-model="form.seed" inputmode="numeric" maxlength="20" pattern="[0-9]{1,20}">
        <div class="fields"><label for="control-steps">Steps<input id="control-steps" v-model.number="form.steps" type="number" min="1" max="150" step="1"></label><label for="control-cfg">CFG<input id="control-cfg" v-model.number="form.cfg" type="number" min="0" max="30" step="any"></label></div>
        <label for="control-sampler">取樣器</label><select id="control-sampler" v-model="form.sampler_name"><option v-if="!capabilities?.sampler_names.includes(form.sampler_name)" :value="form.sampler_name">{{form.sampler_name}}（未確認）</option><option v-for="name in capabilities?.sampler_names" :key="name" :value="name">{{name}}</option></select>
        <label for="control-scheduler">Scheduler</label><select id="control-scheduler" v-model="form.scheduler"><option v-if="!capabilities?.schedulers.includes(form.scheduler)" :value="form.scheduler">{{form.scheduler}}（未確認）</option><option v-for="name in capabilities?.schedulers" :key="name" :value="name">{{name}}</option></select>
        <p class="footnote">固定空 latent／denoise 1，使用 Canny 作結構條件；不以來源 latent 作圖生圖。單次輸出一張。</p>
        <LoraControls v-model="form.loras" :engine-url="form.engine_url" :checkpoint="form.checkpoint" @blocked="loraBlock=$event" />
      </fieldset></form>
      <GenerationPanel :form="form" workflow="control" :blocked-reason="block" :disabled="busy || !!pendingRestore" @busy="generationBusy=$event" @pending="generationPending=$event" @gallery="emit('gallery',$event)" @restore-job="restore('jobs',$event)"/>
    </div>
  </section>
</template>
<style scoped>
.source-preview{margin:18px 0}.source-preview img{max-width:100%;max-height:260px;object-fit:contain}.source-preview figcaption{font-size:12px;line-height:1.7;color:var(--text-secondary)}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:18px;font-size:12px}.control-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:22px;align-items:start}.editor fieldset{border:0;margin:0;padding:0;min-width:0}.editor label{display:block;font-size:12px;margin:18px 0 8px}.editor input,.editor select,.editor textarea{width:100%;box-sizing:border-box;min-width:0}.editor select,.editor textarea{font:inherit;font-size:13px;border:1px solid var(--border-control);border-radius:7px;padding:12px;background:var(--surface-input);color:var(--text-primary)}.editor textarea{line-height:1.8;resize:vertical}.fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}.fields input{margin-top:8px}.footnote{overflow-wrap:anywhere;line-height:1.7}@media(max-width:1100px){.control-grid{grid-template-columns:1fr}}@media(max-width:500px){.fields{grid-template-columns:1fr}}
</style>
