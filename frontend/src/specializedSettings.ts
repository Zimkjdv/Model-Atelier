import type { ControlForm } from './controlSettings'
import { controlEdgeWorkflowId, controlWorkflowId, structureWorkflowId } from './controlSettings'
import type { FeatherForm } from './inpaintSettings'
import { inpaintWorkflowId, inpaintFeatherWorkflowId, fooocusWorkflowId } from './inpaintSettings'
import type { ReferenceForm } from './adapterSettings'
import { referenceWorkflowId } from './adapterSettings'
import type { CreationForm } from './creationSettings'
import type {
  ExperimentVariant,
  ExperimentSummary,
  ExperimentSelection,
} from './experimentSettings'

export type SpecializedFamily = 'inpaint' | 'control' | 'reference'
export type SpecializedForm = FeatherForm | ControlForm | ReferenceForm

export function specializedWorkflow(
  family: SpecializedFamily,
  form: SpecializedForm,
  legacy?: string,
) {
  if (family === 'inpaint') {
    if ('inpaint_model' in form && form.inpaint_model) return fooocusWorkflowId
    return legacy === inpaintWorkflowId &&
      (!('feather_radius' in form) || form.feather_radius === 0)
      ? inpaintWorkflowId
      : inpaintFeatherWorkflowId
  }
  if (family === 'control') {
    if ('control_kind' in form && form.control_kind) return structureWorkflowId
    return legacy === controlWorkflowId ? legacy : controlEdgeWorkflowId
  }
  return referenceWorkflowId
}

export function specializedBody(form: SpecializedForm, workflowId: string): CreationForm {
  const settings: CreationForm &
    Partial<Pick<FeatherForm, 'feather_radius'> & Pick<ControlForm, 'canny_low' | 'canny_high'>> = {
    ...form,
  }
  if (workflowId === inpaintWorkflowId) delete settings.feather_radius
  if (workflowId === structureWorkflowId) {
    delete settings.canny_low
    delete settings.canny_high
  }
  return settings as CreationForm
}

export type SpecializedDocument = {
  kind: 'model-atelier-specialized-creation'
  schema_version: 1
  workflow_id: string
  settings: SpecializedForm
  input_assets: {
    role: 'source' | 'mask'
    id: string
    sha256: string
    size: number
    width: number
    height: number
  }[]
  registrations: Record<string, unknown>
  source_snapshot?: unknown
}
export type SpecializedDraft = SpecializedDocument & { id: string; revision: number }
export type SpecializedPreview = {
  document: SpecializedDocument
  warnings: string[]
  loadable: boolean
}
export type SpecializedPlan = {
  kind: 'model-atelier-specialized-comparison'
  title: string
  workflow_id: string
  plan_sha256: string
  axis: string
  values: (number | string)[]
  variants: ExperimentVariant[]
  document: SpecializedDocument
}
export type SpecializedPlanRecord = {
  id: string
  revision: number
  archived: boolean
  plan: SpecializedPlan
}
export type SpecializedPlanSummary = Omit<ExperimentSummary, 'workflow_id'> & {
  workflow_id: string
}
export function variantDocument(
  plan: SpecializedPlan,
  variant: ExperimentVariant,
): SpecializedDocument {
  return { ...plan.document, settings: variant.settings as SpecializedForm, source_snapshot: null }
}
export function selectionFor(
  record: SpecializedPlanRecord,
  variant: ExperimentVariant,
): ExperimentSelection {
  return { plan_id: record.id, plan_sha256: record.plan.plan_sha256, variant_id: variant.id }
}
