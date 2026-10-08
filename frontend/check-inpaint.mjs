import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import ts from 'typescript'
const modules={}
for(const name of ['referenceSettings','creationSettings','inpaintSettings']) {
  const source=await readFile(new URL('./src/'+name+'.ts',import.meta.url),'utf8')
  let compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
  for(const [dependency,url] of Object.entries(modules)) compiled=compiled.replaceAll("'./"+dependency+"'",JSON.stringify(url))
  modules[name]='data:text/javascript;base64,'+Buffer.from(compiled).toString('base64')
}
const {newInpaint,chooseSource,chooseMask,copyInpaint,inpaintProblem,maskPoint,binaryMask}=await import(modules.inpaintSettings)
const form=newInpaint();form.engine_url='http://127.0.0.1:8188';form.checkpoint='test';form.seed='18446744073709551615'
chooseSource(form,'source');chooseMask(form,'mask')
const source={id:'source',width:80,height:64,archived:false},mask={id:'mask',width:80,height:64,archived:false}
assert.equal(inpaintProblem(form,source,mask),'')
assert.notEqual(inpaintProblem(form,source,{...mask,width:64}),'')
assert.notEqual(inpaintProblem(form,{...source,archived:true},mask),'')
for(const change of [{seed:'18446744073709551616'},{seed:'1e2'},{seed:'01'},{width:8192,height:8192},{width:65},{grow_mask_by:65},{grow_mask_by:1.5},{denoise:NaN},{cfg:Infinity},{steps:0},{reference_ids:['mask','source']}]) assert.notEqual(inpaintProblem({...form,...change},source,mask),'')
const frozen=copyInpaint(form),pending=JSON.parse(JSON.stringify({...frozen,request_id:'original'}))
form.loras.push({name:'first',enabled:true,strength_model:0.5,strength_clip:1})
chooseSource(form,'new-source')
assert.equal(form.mask_asset_id,null);assert.deepEqual(form.reference_ids,[])
assert.equal(frozen.seed,'18446744073709551615');assert.deepEqual(frozen.reference_ids,['source','mask']);assert.deepEqual(frozen.loras,[])
assert.equal(pending.mask_asset_id,'mask');assert.equal(pending.request_id,'original');assert.equal(pending.seed,'18446744073709551615')
assert.throws(()=>copyInpaint({...frozen,mask_asset_id:null}));assert.throws(()=>copyInpaint({...frozen,seed:9007199254740993}));assert.throws(()=>copyInpaint({...frozen,reference_ids:['source']}))
const retained=newInpaint();chooseSource(retained,'source');chooseMask(retained,'mask');chooseSource(retained,'source');assert.equal(retained.mask_asset_id,'mask')
assert.deepEqual(maskPoint(110,60,{left:10,top:10,width:200,height:100},80,64),{x:40,y:32})
assert.deepEqual(maskPoint(-10,999,{left:10,top:10,width:200,height:100},80,64),{x:0,y:64})
assert.throws(()=>maskPoint(0,0,{left:0,top:0,width:0,height:1},80,64))
const rgba=new Uint8ClampedArray([127,127,127,255,128,128,128,255,0,0,0,0,0,0,0,255])
assert.equal(binaryMask(rgba),2);assert.deepEqual([...rgba],[0,0,0,255,255,255,255,255,255,255,255,255,0,0,0,255])
assert.equal(binaryMask(rgba,true),2);assert.deepEqual([...rgba],[255,255,255,255,0,0,0,255,0,0,0,255,255,255,255,255]);assert.throws(()=>binaryMask(new Uint8ClampedArray(1)))
console.log('Inpainting source changes, dimensions, exact seed, immutable restoration, pointer coordinates and binary-mask checks passed.')

const {uploadMaskAsset}=await import(modules.inpaintSettings)
const blob=new Blob(['PNG bytes'],{type:'image/png'})
let observed=false
const saved=await uploadMaskAsset(blob,'遮罩 example.png',async(url,options)=>{
  assert.equal(new URL(url,'http://local').searchParams.get('filename'),'遮罩 example.png');assert.equal(options.method,'POST');assert.equal(options.body,blob);assert.equal(options.headers['Content-Type'],'application/octet-stream');observed=true
  return Response.json({id:'mask',width:80,height:64,archived:false})
})
assert.equal(observed,true);assert.equal(saved.id,'mask')
await assert.rejects(()=>uploadMaskAsset(blob,'mask.png',async()=>Response.json({detail:'invalid image'},{status:422})),/invalid image/)
await assert.rejects(()=>uploadMaskAsset(blob,'mask.png',async()=>Response.json({id:'mask'})),/格式/)
console.log('Raw image-body asset upload and error contract checks passed.')
