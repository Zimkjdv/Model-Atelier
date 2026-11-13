import type { InjectionKey, Ref } from 'vue'
import { referenceWorkflowId } from './adapterSettings'
import { isControlWorkflow } from './controlSettings'
import { isInpaintWorkflow } from './inpaintSettings'
import { fluxWorkflowId } from './fluxSettings'
import { isFluxExtension } from './fluxExtensions'
import type { Job } from './jobEvents'

export type GenerationFamily =
  'checkpoint' | 'flux' | 'flux-addon' | 'inpaint' | 'control' | 'reference'

export function generationFamily(job: Job): GenerationFamily {
  const id = job.workflow_id
  if (id === referenceWorkflowId) return 'reference'
  if (isControlWorkflow(id)) return 'control'
  if (isInpaintWorkflow(id)) return 'inpaint'
  if (id === fluxWorkflowId) return 'flux'
  if (isFluxExtension(id)) return 'flux-addon'
  return 'checkpoint'
}

export const jobStatusLabels: Record<string, string> = {
  uploading_input: '上傳輸入圖片中',
  validating: '確認模型中',
  submitting: '提交中',
  queued: '等待生成',
  running: '生成中',
  completed: '已完成',
  failed: '失敗',
  unknown: '結果待確認',
  cancelling: '確認取消中',
  cancel_unknown: '取消結果待確認',
  cancelled: '已取消排隊',
  stopping: '確認停止中',
  stop_unknown: '停止結果待確認',
  stopped: '已停止生成',
}

export const generationNavigation: InjectionKey<{
  drawerOpen: Ref<boolean>
  target: Ref<{ job: Job } | null>
  refreshOverview: () => void
}> = Symbol('generation navigation')
