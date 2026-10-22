import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'
const source = await readFile(new URL('./src/experimentSettings.ts',import.meta.url),'utf8')
const compiled = ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
const {matchesExperiment,experimentForSubmission} = await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'))
const settings={title:'原組',prompt:'chair',seed:'9007199254740993',cfg:5,loras:[{name:'one',enabled:true,strength_model:1,strength_clip:1},{name:'two',enabled:false,strength_model:0.5,strength_clip:0}],reference_ids:['original'],image_asset_id:'original',reference_resize:'fit'}
const load={settings:structuredClone(settings),archived:false,selection:{plan_id:'plan',plan_sha256:'hash',variant_id:'variant-1'}}
const reversedKeys=Object.fromEntries(Object.entries(settings).reverse())
assert.equal(matchesExperiment(load,reversedKeys),true)
for(const changed of [{seed:'9007199254740992'},{title:'changed'},{cfg:4},{reference_resize:'stretch'},{reference_ids:['other']},{loras:[...settings.loras].reverse()},{loras:[settings.loras[0],{...settings.loras[1],strength_clip:1}]}]) {
  const form={...settings,...changed}
  assert.equal(matchesExperiment(load,form),false)
  assert.throws(() => experimentForSubmission(load,form))
}
assert.equal(experimentForSubmission(null,settings),null)
assert.throws(() => experimentForSubmission({...load,archived:true},settings))
const snapshot=experimentForSubmission(load,settings)
snapshot.variant_id='variant-2'
assert.equal(load.selection.variant_id,'variant-1')
// The request body persists the original association even after the form changes.
const pending=JSON.parse(JSON.stringify({...settings,request_id:'original-id',experiment:experimentForSubmission(load,settings)}))
settings.seed='18446744073709551615'
assert.equal(pending.seed,'9007199254740993')
assert.equal(pending.experiment.variant_id,'variant-1')
console.log('Experiment settings, disabled LoRA order, exact seed, archive and immutable request checks passed.')

const reportSource=await readFile(new URL('./src/experimentReport.ts',import.meta.url),'utf8')
const reportCompiled=ts.transpileModule(reportSource,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
const {checkedExperimentReport}=await import('data:text/javascript;base64,'+Buffer.from(reportCompiled).toString('base64'))
const record={id:'plan',plan:{plan_sha256:'a'.repeat(64),variants:[{},{}]}}
const value={kind:'model-atelier-comparison-results',schema_version:1,source:'saved-platform-records',plan:record,variants:[{},{}],seed:'18446744073709551615'}
async function response(value,overrides={}) {
  const raw=new TextEncoder().encode(JSON.stringify(value)),hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(v=>v.toString(16).padStart(2,'0')).join('')
  return new Response(raw,{headers:{'Content-Type':'application/json','X-Atelier-SHA256':hash,...overrides}})
}
const reportBlob=await checkedExperimentReport(await response(value),record)
assert.equal(JSON.parse(await reportBlob.text()).seed,'18446744073709551615')
for(const change of [{schema_version:true},{kind:'model-atelier-comparison-plan'},{source:'engine'},{plan:{...record,id:'other'}},{variants:[{}]}]) await assert.rejects(()=>response({...value,...change}).then(r=>checkedExperimentReport(r,record)))
await assert.rejects(()=>response(value,{'X-Atelier-SHA256':'b'.repeat(64)}).then(r=>checkedExperimentReport(r,record)),/SHA256/)
await assert.rejects(()=>checkedExperimentReport(Response.json({detail:'report too large'},{status:413}),record),/report too large/)
await assert.rejects(()=>checkedExperimentReport(new Response(new ReadableStream({pull(c){c.enqueue(new Uint8Array(1024*1024))}})),record),/大小上限/)
console.log('Result report source/plan/version/hash, exact seed, explicit errors and bounded download passed.')

// Parsed JS numbers are only inspected for metadata; export the original bytes unchanged.
const exactText=JSON.stringify({...value,workflow:{seed:'__exact_large_seed__'}}).replace('"__exact_large_seed__"','18446744073709551615')
const exactRaw=new TextEncoder().encode(exactText),exactHash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',exactRaw))].map(v=>v.toString(16).padStart(2,'0')).join('')
const exactBlob=await checkedExperimentReport(new Response(exactRaw,{headers:{'Content-Type':'application/json','X-Atelier-SHA256':exactHash}}),record)
assert.equal(await exactBlob.text(),exactText)
console.log('Original report bytes preserve workflow integers beyond JavaScript safe range.')
