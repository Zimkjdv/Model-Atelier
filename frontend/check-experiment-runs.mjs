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
