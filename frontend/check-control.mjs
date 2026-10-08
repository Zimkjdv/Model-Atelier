import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'
const modules={}
for(const name of ['referenceSettings','creationSettings','controlSettings']) {
  const source=await readFile(new URL('./src/'+name+'.ts',import.meta.url),'utf8')
  let compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
  for(const [dependency,url] of Object.entries(modules)) compiled=compiled.replaceAll("'./"+dependency+"'",JSON.stringify(url))
  modules[name]='data:text/javascript;base64,'+Buffer.from(compiled).toString('base64')
}
const {newControl,chooseSource,controlProblem,registeredControlProblem,copyControl}=await import(modules.controlSettings)
const source={id:'source',archived:false,width:80,height:64}
const form=newControl();form.engine_url='http://127.0.0.1:8188';form.checkpoint='checkpoint';form.control_net_name='control';form.seed='18446744073709551615';chooseSource(form,'source')
assert.equal(controlProblem(form,source),'')
for(const change of [{seed:'18446744073709551616'},{seed:'1e2'},{seed:'01'},{seed:9007199254740993},{width:8192,height:8192},{width:65},{steps:1.5},{cfg:Infinity},{control_strength:0},{control_strength:true},{control_strength:NaN},{control_start:0.5,control_end:0.5},{control_end:1.1},{canny_low:0.009},{canny_high:Infinity},{canny_low:0.8,canny_high:0.8},{workflow_mode:'image2image'},{denoise:0.5},{reference_ids:[]},{reference_resize:'crop'}]) assert.notEqual(controlProblem({...form,...change},source),'')
assert.notEqual(controlProblem(form,{...source,archived:true}),'')
form.loras=[{name:'first',enabled:true,strength_model:0.5,strength_clip:1},{name:'second',enabled:false,strength_model:0.25,strength_clip:0.9}]
const copied=copyControl(form),pending=JSON.parse(JSON.stringify({...copied,request_id:'original'}))
chooseSource(form,'new-source');form.control_strength=0.9;form.loras.reverse()
assert.deepEqual(copied.reference_ids,['source']);assert.equal(copied.control_strength,0.5);assert.equal(copied.loras[0].name,'first');assert.equal(pending.seed,'18446744073709551615');assert.equal(pending.request_id,'original');assert.equal(pending.image_asset_id,'source')
for(const change of [{control_end:0},{control_net_name:''},{seed:5},{mask_asset_id:'mask'},{workflow_mode:'image2image'},{loras:[{name:'x',enabled:true,strength_model:NaN,strength_clip:1}]}]) assert.throws(()=>copyControl({...copied,...change}))
const missing={...copied};delete missing.canny_high;assert.throws(()=>copyControl(missing))
const library={engine_url:form.engine_url,synced_at:'time',sync_error:null,controlnets:[{name:'control',listed:true,kind:'canny',architecture:'sdxl'}]}
assert.equal(registeredControlProblem(library,form.engine_url,'control','sdxl'),'')
for(const [lib,engine,name,arch] of [[null,form.engine_url,'control','sdxl'],[{...library,sync_error:'offline'},form.engine_url,'control','sdxl'],[library,'other','control','sdxl'],[library,form.engine_url,'absent','sdxl'],[library,form.engine_url,'control','sd1'],[library,form.engine_url,'control','unknown'],[{...library,controlnets:[{...library.controlnets[0],kind:'depth'}]},form.engine_url,'control','sdxl'],[{...library,controlnets:[{...library.controlnets[0],listed:false}]},form.engine_url,'control','sdxl']]) assert.notEqual(registeredControlProblem(lib,engine,name,arch),'')
console.log('Canny bounds, architecture/kind isolation, exact seed, complete restoration and immutable pending checks passed.')
