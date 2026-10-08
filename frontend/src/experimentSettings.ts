import type { CreationForm } from './creationSettings'
export type ExperimentCase = { id:string; name:string; prompt:string; character_key:string|null; checks:string[] }
export type ExperimentSuite = { id:string; version:number; name:string; sha256:string; cases:ExperimentCase[] }
export type ExperimentVariant = { id:string; case_id:string; value:string|number; settings:CreationForm }
export type ComparisonPlan = {
  kind:'model-atelier-comparison-plan'; schema_version:1; title:string
  workflow_id:'checkpoint-text2image-v1'|'checkpoint-image2image-v1'
  plan_sha256:string; baseline:CreationForm; expected_job_count:number; batch_size:1
  axis:string; values:(string|number)[]; target_lora?:string; suite:ExperimentSuite|null
  variants:ExperimentVariant[]; warnings:string[]
}
export type ExperimentSummary = {
  id:string; revision:number; archived:boolean; title:string; workflow_id:ComparisonPlan['workflow_id']
  plan_sha256:string; axis:string; expected_job_count:number; created_at:string; updated_at:string
}
export type SavedExperiment = { id:string; revision:number; archived:boolean; created_at:string; updated_at:string; plan:ComparisonPlan }

export type ExperimentSelection = { plan_id:string; plan_sha256:string; variant_id:string }
export type ExperimentLoad = { selection:ExperimentSelection; plan_title:string; archived:boolean; settings:CreationForm }
export type ExperimentContext = ExperimentSelection & { schema_version:1; plan_title:string; workflow_id:ComparisonPlan['workflow_id']; axis:string; target_lora?:string|null; case_id:string; value:string|number; settings:CreationForm }
export type ExperimentOutput = { id:string; title:string; width:number; height:number; sha256:string; archived:boolean; image_available:boolean; thumbnail_available:boolean }
export type ExperimentRun = { id:string; status:string; error?:string|null; created_at:string; model_version:string; artworks:ExperimentOutput[] }
export type ExperimentResults = { plan_id:string; plan_sha256:string; archived:boolean; variants:{variant_id:string; case_id:string; value:string|number; runs:ExperimentRun[]}[] }

export function canonicalExperimentSettings(value:unknown):string {
  if(Array.isArray(value)) return '['+value.map(canonicalExperimentSettings).join(',')+']'
  if(value !== null && typeof value === 'object') return '{'+Object.keys(value).sort().map(key => JSON.stringify(key)+':'+canonicalExperimentSettings((value as Record<string,unknown>)[key])).join(',')+'}'
  return JSON.stringify(value) ?? 'null'
}
export function matchesExperiment(load:ExperimentLoad, settings:unknown):boolean {
  return canonicalExperimentSettings(load.settings) === canonicalExperimentSettings(settings)
}
export function experimentForSubmission(load:ExperimentLoad|null|undefined, settings:unknown):ExperimentSelection|null {
  if(!load) return null
  if(load.archived) throw new Error('比較方案已封存，請還原並重新載入該組，或解除關聯再生成。')
  if(!matchesExperiment(load,settings)) throw new Error('設定已與比較組不同；請重新載入原組或解除關聯再生成。')
  return {...load.selection}
}
