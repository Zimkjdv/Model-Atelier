import { newCreation, type CreationForm } from './creationSettings'
import type { ReferenceAsset } from './referenceSettings'
import type { ModelMetadata, ModelMetadataSnapshot } from './modelMetadata'
export const controlWorkflowId = 'checkpoint-canny-controlnet-v1'
export type ControlForm = CreationForm & { workflow_mode: 'text2image'; control_net_name: string; control_strength: number; control_start: number; control_end: number; canny_low: number; canny_high: number }
export type ControlModel = ModelMetadata & { name: string; listed: boolean; version: string; source_url: string; notes: string; kind: string }
export type ControlCatalog = { engine_url: string; controlnets: ControlModel[]; synced_at: string | null; sync_error: string | null }
export type ControlMetadata = ModelMetadataSnapshot & { role: string; kind?: string }
export function newControl(): ControlForm {
  return { ...newCreation(), title: '未命名結構參考', workflow_mode: 'text2image', control_net_name: '', control_strength: 0.5, control_start: 0, control_end: 1, canny_low: 0.4, canny_high: 0.8 }
}
export function chooseSource(form: ControlForm, id: string | null) { form.image_asset_id=id;form.reference_ids=id?[id]:[] }
export function controlProblem(form: ControlForm, source?: ReferenceAsset): string {
  if (!source || source.archived || source.id !== form.image_asset_id || JSON.stringify(form.reference_ids)!==JSON.stringify([source.id])) return '請選擇存在、未封存且關聯一致的結構參考素材。'
  if (form.workflow_mode!=='text2image' || form.denoise!==1) return '結構條件固定使用空 latent、denoise 1。'
  if (!form.control_net_name.trim()) return '請選擇 Canny 控制模型。'
  if (!form.title.trim() || form.title.length>100 || form.prompt.length>20000 || form.negative_prompt.length>20000) return '請確認名稱與提示詞長度。'
  if ([form.width,form.height].some(v=>!Number.isInteger(v)||v<64||v>8192||v%8) || form.width*form.height>16000000) return '尺寸需為 64–8192 的 8 倍數，且不超過 1600 萬像素。'
  if (typeof form.seed!=='string' || !/^(0|[1-9][0-9]{0,19})$/.test(form.seed) || BigInt(form.seed)>18446744073709551615n) return 'Seed 需為 64 位非負整數字串。'
  if (!Number.isInteger(form.steps)||form.steps<1||form.steps>150||!Number.isFinite(form.cfg)||form.cfg<0||form.cfg>30) return '請確認 steps 1–150 與 CFG 0–30。'
  if (!Number.isFinite(form.control_strength)||form.control_strength<=0||form.control_strength>10) return '控制強度需大於 0 且不超過 10。'
  if ([form.control_start,form.control_end].some(v=>!Number.isFinite(v)||v<0||v>1)||form.control_start>=form.control_end) return '作用範圍需在 0–1，起始小於結束。'
  if ([form.canny_low,form.canny_high].some(v=>!Number.isFinite(v)||v<0.01||v>0.99)||form.canny_low>=form.canny_high) return 'Canny 閾值需在 0.01–0.99，低閾值小於高閾值。'
  if (!['fit','stretch'].includes(form.reference_resize)) return '請確認素材縮放方式。'
  return ''
}
export function registeredControlProblem(library: ControlCatalog|null, engine: string, name: string, architecture: unknown): string {
  if (!library || library.engine_url!==engine || !library.synced_at || library.sync_error) return '控制模型清單未確認，請到模型庫成功同步後更新。'
  const model=library.controlnets.find(m=>m.name===name)
  if (!model?.listed) return '所選控制模型不在最近成功同步的清單。'
  if (model.kind!=='canny' || !['sd1','sdxl'].includes(String(architecture)) || model.architecture!==architecture) return '控制模型需登記 canny 類型，且與 checkpoint 同為 SD 1.x 或 SDXL。'
  return ''
}
export function copyControl(value: ControlForm): ControlForm {
  try {
    const keys=Object.keys(newControl())
    if (!value || Object.keys(value).length!==keys.length || keys.some(k=>!(k in value))) throw new Error()
    if (['title','prompt','negative_prompt','engine_url','checkpoint','control_net_name','sampler_name','scheduler','seed'].some(k=>typeof (value as unknown as Record<string,unknown>)[k]!=='string') || !value.engine_url || !value.checkpoint || !value.image_asset_id) throw new Error()
    if (!Array.isArray(value.loras)||value.loras.length>4 || new Set(value.loras.map(v=>v.name)).size!==value.loras.length || value.loras.some(v=>!v.name?.trim()||typeof v.enabled!=='boolean'||[v.strength_model,v.strength_clip].some(n=>!Number.isFinite(n)||n< -10||n>10))) throw new Error()
    if (controlProblem(value,{id:value.image_asset_id,title:'',width:0,height:0,purpose:'unspecified',archived:false})) throw new Error()
    return JSON.parse(JSON.stringify(value))
  } catch { throw new Error('不是完整 Canny 結構參考設定，未載入部分內容。') }
}
