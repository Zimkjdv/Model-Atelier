import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'
const modules={}
for(const name of ['referenceSettings','creationSettings','controlSettings','controlEdges','cannyPreview']) {
  const source=await readFile(new URL('./src/'+name+'.ts',import.meta.url),'utf8')
  let compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
  for(const [dependency,url] of Object.entries(modules)) compiled=compiled.replaceAll("'./"+dependency+"'",JSON.stringify(url))
  modules[name]='data:text/javascript;base64,'+Buffer.from(compiled).toString('base64')
}
const {newControl,chooseSource,controlProblem,registeredControlProblem,copyControl,controlSubmission,controlWorkflowId,controlEdgeWorkflowId,controlPendingMarker,isControlWorkflow}=await import(modules.controlSettings)
const source={id:'source',archived:false,width:80,height:64}
const form=newControl();form.engine_url='http://127.0.0.1:8188';form.checkpoint='checkpoint';form.control_net_name='control';form.seed='18446744073709551615';chooseSource(form,'source')
assert.equal(controlProblem(form,source),'')
for(const change of [{seed:'18446744073709551616'},{seed:'1e2'},{seed:'01'},{seed:9007199254740993},{width:8192,height:8192},{width:65},{steps:1.5},{cfg:Infinity},{control_strength:0},{control_strength:true},{control_strength:NaN},{control_start:0.5,control_end:0.5},{control_end:1.1},{canny_low:0.009},{canny_high:Infinity},{canny_low:0.8,canny_high:0.8},{workflow_mode:'image2image'},{denoise:0.5},{reference_ids:[]},{reference_resize:'crop'}]) assert.notEqual(controlProblem({...form,...change},source),'')
assert.notEqual(controlProblem(form,{...source,archived:true}),'')
form.loras=[{name:'first',enabled:true,strength_model:0.5,strength_clip:1},{name:'second',enabled:false,strength_model:0.25,strength_clip:0.9}]
const limits=copyControl({...form,loras:[{name:'boundary',enabled:true,strength_model:20,strength_clip:-20}]});assert.equal(limits.loras[0].strength_model,20);assert.equal(limits.loras[0].strength_clip,-20);assert.throws(()=>copyControl({...limits,loras:[{...limits.loras[0],strength_model:20.01}]}))
const copied=copyControl(form),pending=JSON.parse(JSON.stringify({...copied,request_id:'original'}))
chooseSource(form,'new-source');form.control_strength=0.9;form.loras.reverse()
assert.deepEqual(copied.reference_ids,['source']);assert.equal(copied.control_strength,0.5);assert.equal(copied.loras[0].name,'first');assert.equal(pending.seed,'18446744073709551615');assert.equal(pending.request_id,'original');assert.equal(pending.image_asset_id,'source')
for(const change of [{control_end:0},{control_net_name:''},{seed:5},{mask_asset_id:'mask'},{workflow_mode:'image2image'},{loras:[{name:'x',enabled:true,strength_model:NaN,strength_clip:1}]}]) assert.throws(()=>copyControl({...copied,...change}))
const missing={...copied};delete missing.canny_high;assert.throws(()=>copyControl(missing))
const library={engine_url:form.engine_url,synced_at:'time',sync_error:null,controlnets:[{name:'control',listed:true,kind:'canny',architecture:'sdxl'}]}
assert.equal(registeredControlProblem(library,form.engine_url,'control','sdxl'),'')
for(const [lib,engine,name,arch] of [[null,form.engine_url,'control','sdxl'],[{...library,sync_error:'offline'},form.engine_url,'control','sdxl'],[library,'other','control','sdxl'],[library,form.engine_url,'absent','sdxl'],[library,form.engine_url,'control','sd1'],[library,form.engine_url,'control','unknown'],[{...library,controlnets:[{...library.controlnets[0],kind:'depth'}]},form.engine_url,'control','sdxl'],[{...library,controlnets:[{...library.controlnets[0],listed:false}]},form.engine_url,'control','sdxl']]) assert.notEqual(registeredControlProblem(lib,engine,name,arch),'')
// A stored legacy request must retain its old route and every original body field.
const legacy=JSON.parse(JSON.stringify(pending)),legacyBefore=JSON.stringify(legacy)
assert.deepEqual(controlSubmission(legacy),{path:'/api/control/generate',body:legacy})
assert.equal(JSON.stringify(legacy),legacyBefore)
const modern={...legacy,[controlPendingMarker]:controlEdgeWorkflowId},modernBefore=JSON.stringify(modern)
assert.deepEqual(controlSubmission(modern),{path:'/api/control-edge/generate',body:legacy})
assert.equal(JSON.stringify(modern),modernBefore);assert.equal(controlSubmission(modern).body.seed,'18446744073709551615')
for(const version of ['unknown',null,undefined,1]) assert.throws(()=>controlSubmission({...legacy,[controlPendingMarker]:version}))
for(const value of [null,[],5,'saved']) assert.throws(()=>controlSubmission(value))
assert.ok(isControlWorkflow(controlWorkflowId));assert.ok(isControlWorkflow(controlEdgeWorkflowId));assert.equal(isControlWorkflow('unknown'),false)
const {edgeMetadata}=await import(modules.controlEdges),id='11111111-1111-4111-8111-111111111111'
const unsaved={job_id:id,workflow_id:controlEdgeWorkflowId,state:'not_saved',image_available:false,import_allowed:true,message:'original'}
assert.deepEqual(edgeMetadata(unsaved,id),unsaved)
const saved={...unsaved,state:'saved',image_available:true,import_allowed:false,sha256:'a'.repeat(64),size_bytes:123,width:768,height:768,edge_pixels:0,total_pixels:768*768,saved_at:'2026-10-09T00:00:00Z',anchor:{workflow_sha256:'b'.repeat(64)},source:{node_id:'16',type:'output',filename:'canny_00001_.png',subfolder:'model_atelier/'+id}}
assert.equal(edgeMetadata(saved,id).edge_pixels,0)
assert.equal(edgeMetadata({...saved,source:{...saved.source,subfolder:'model_atelier'+String.fromCharCode(92)+id}},id).state,'saved')
assert.equal(edgeMetadata({...saved,state:'unavailable',image_available:false},id).state,'unavailable')
for(const change of [{job_id:'other'},{workflow_id:controlWorkflowId},{state:'unknown'},{image_available:false},{import_allowed:true},{sha256:'bad'},{size_bytes:32*1024*1024+1},{width:8193},{edge_pixels:-1},{edge_pixels:768*768+1},{edge_pixels:true},{total_pixels:64},{anchor:{workflow_sha256:'wrong'}},{source:{...saved.source,node_id:'7'}},{source:{...saved.source,subfolder:'other'}},{source:{...saved.source,filename:'../canny.png'}},{source:null}]) assert.throws(()=>edgeMetadata({...saved,...change},id))
assert.throws(()=>edgeMetadata({...unsaved,image_available:true},id))
console.log('Canny bounds, v1/v2 pending recovery, exact seed, complete restoration and immutable edge source checks passed.')

const {cannyPreviewInput,cannyPreviewIdentity,cannyPreviewProblem,checkedCannyPreview,cannyPreviewMethod}=await import(modules.cannyPreview)
const previewSource={...source,id:'00000000-0000-4000-8000-000000000001',sha256:'a'.repeat(64)}
const previewForm={...copied,image_asset_id:previewSource.id,width:64,height:64,canny_low:.4,canny_high:.8,reference_resize:'fit'}
assert.equal(cannyPreviewProblem(previewForm,previewSource),'')
assert.equal(cannyPreviewProblem({...previewForm,checkpoint:'',engine_url:'',control_net_name:'',prompt:'',seed:'invalid'},previewSource),'')
for(const change of [{width:2048,height:2048},{width:65},{canny_low:true},{canny_low:NaN},{canny_high:.4},{reference_resize:'crop'}]) assert.notEqual(cannyPreviewProblem({...previewForm,...change},previewSource),'')
for(const change of [{archived:true},{sha256:undefined},{id:'other'}]) assert.notEqual(cannyPreviewProblem(previewForm,{...previewSource,...change}),'')
assert.deepEqual(Object.keys(cannyPreviewInput(previewForm)).sort(),['canny_high','canny_low','height','image_asset_id','reference_resize','width'])
const identity=cannyPreviewIdentity(previewForm,previewSource)
assert.equal(cannyPreviewIdentity({...previewForm,prompt:'other',seed:'2',control_strength:1},previewSource),identity)
for(const change of [{width:128},{height:128},{canny_low:.3},{canny_high:.9},{reference_resize:'stretch'},{image_asset_id:'other'}]) assert.notEqual(cannyPreviewIdentity({...previewForm,...change},previewSource),identity)
assert.notEqual(cannyPreviewIdentity(previewForm,{...previewSource,sha256:'b'.repeat(64)}),identity)
const raw=Uint8Array.from(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAfElEQVR4nNXOQREAIADDsFLlk44IHlyjIGcbZRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncf4OvLqiLAIAzKKwUwAAAABJRU5ErkJggg==','base64'))
const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(v=>v.toString(16).padStart(2,'0')).join('')
const info={...cannyPreviewInput(previewForm),method:cannyPreviewMethod,device:'cpu',dtype:'float32',native_sha256:'5efd352d92d7749b7b9734a1676fee18f4431d44a8e9477822a7a8f38ad26051',torch:'test',kornia:'test',pillow:'test',asset_sha256:previewSource.sha256,sha256:hash,input_sha256:'b'.repeat(64),preprocessing:{id:'checkpoint-image-input',version:1,sha256:'b'.repeat(64),width:64,height:64,resize:'fit',resampling:'LANCZOS',background:'#ffffff',output_mode:'RGB',output_format:'PNG',library_version:'test'}}
const headers=value=>({'Content-Type':'image/png','X-Atelier-SHA256':hash,'X-Atelier-Width':'64','X-Atelier-Height':'64','X-Atelier-Canny-Provenance':Buffer.from(JSON.stringify(value)).toString('base64')})
assert.equal((await checkedCannyPreview(new Response(raw,{headers:headers(info)}),previewForm,previewSource)).blob.size,raw.length)
for(const change of [{method:'unknown'},{device:'cuda'},{canny_low:.5},{image_asset_id:'other'},{asset_sha256:'c'.repeat(64)},{native_sha256:'c'.repeat(64)},{preprocessing:{...info.preprocessing,sha256:'c'.repeat(64)}},{preprocessing:{...info.preprocessing,version:true}},{torch:'invalid\n'}]) await assert.rejects(()=>checkedCannyPreview(new Response(raw,{headers:headers({...info,...change})}),previewForm,previewSource))
for(const change of [{'Content-Type':'text/html'},{'X-Atelier-Width':'65'},{'X-Atelier-SHA256':'c'.repeat(64)},{'X-Atelier-Canny-Provenance':'!!!!'}]) await assert.rejects(()=>checkedCannyPreview(new Response(raw,{headers:{...headers(info),...change}}),previewForm,previewSource))
const changed=new Uint8Array(raw);changed[40]^=1
await assert.rejects(()=>checkedCannyPreview(new Response(changed,{headers:headers(info)}),previewForm,previewSource),/SHA256/)
await assert.rejects(()=>checkedCannyPreview(Response.json({detail:'preview busy'},{status:409}),previewForm,previewSource),/preview busy/)
await assert.rejects(()=>checkedCannyPreview(new Response(new ReadableStream({pull(c){c.enqueue(new Uint8Array(1024*1024))}}),{headers:headers(info)}),previewForm,previewSource),/大小上限/)
console.log('CPU Canny preview input isolation, source/version/PNG/hash checks, bounded streams and stale identity passed.')
