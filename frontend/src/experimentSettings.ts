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
