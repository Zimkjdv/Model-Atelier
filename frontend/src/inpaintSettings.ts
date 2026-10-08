import { newCreation, type CreationForm } from './creationSettings'
import type { ReferenceAsset } from './referenceSettings'
export const inpaintWorkflowId = 'checkpoint-inpaint-v1'
export type InpaintForm = CreationForm & { workflow_mode: 'image2image'; mask_asset_id: string | null; grow_mask_by: number }
export function newInpaint(): InpaintForm {
  return { ...newCreation(), title: '未命名局部編輯', workflow_mode: 'image2image', mask_asset_id: null, grow_mask_by: 6 }
}
export function chooseSource(form: InpaintForm, id: string | null) {
  if (form.image_asset_id === id) return
  form.image_asset_id = id; form.mask_asset_id = null; form.reference_ids = []
}
export function chooseMask(form: InpaintForm, id: string | null) {
  form.mask_asset_id = id
  form.reference_ids = form.image_asset_id && id ? [form.image_asset_id, id] : []
}
export function inpaintProblem(form: InpaintForm, source?: ReferenceAsset, mask?: ReferenceAsset) {
  if (!source || source.archived || source.id !== form.image_asset_id) return '請選擇存在且未封存的原圖。'
  if (!mask || mask.archived || mask.id !== form.mask_asset_id) return '請繪製並保存遮罩，或選擇一張已保存的遮罩。'
  if (source.id === mask.id || source.width !== mask.width || source.height !== mask.height) return '遮罩須為另一張素材，且與原圖尺寸完全相同。'
  if (JSON.stringify(form.reference_ids) !== JSON.stringify([source.id, mask.id])) return '原圖與遮罩關聯不同，請重新選擇。'
  if (!form.title.trim() || form.title.length > 100 || form.prompt.length > 20000 || form.negative_prompt.length > 20000) return '請確認名稱與提示詞長度。'
  if ([form.width, form.height].some(v => !Number.isInteger(v) || v < 64 || v > 8192 || v % 8) || form.width * form.height > 16000000) return '尺寸需為 64–8192 的 8 倍數，且不超過 1600 萬像素。'
  if (!/^(0|[1-9][0-9]{0,19})$/.test(form.seed) || BigInt(form.seed) > 18446744073709551615n) return 'Seed 需為 0 至 18446744073709551615 的整數字串。'
  if (!Number.isInteger(form.grow_mask_by) || form.grow_mask_by < 0 || form.grow_mask_by > 64) return '遮罩擴張需為 0–64 的整數。'
  if (!Number.isInteger(form.steps) || form.steps < 1 || form.steps > 150 || !Number.isFinite(form.cfg) || form.cfg < 0 || form.cfg > 30 || !Number.isFinite(form.denoise) || form.denoise < 0 || form.denoise > 1) return '請確認 steps 1–150、CFG 0–30 與 denoise 0–1。'
  return ''
}
export function copyInpaint(value: InpaintForm): InpaintForm {
  if (value.workflow_mode !== 'image2image' || !value.image_asset_id || !value.mask_asset_id || value.image_asset_id === value.mask_asset_id || JSON.stringify(value.reference_ids) !== JSON.stringify([value.image_asset_id,value.mask_asset_id]) || typeof value.seed !== 'string' || !Number.isInteger(value.grow_mask_by)) throw new Error('不是完整局部編輯設定，未載入部分內容。')
  return JSON.parse(JSON.stringify(value))
}
export function maskPoint(x: number, y: number, rect: { left: number; top: number; width: number; height: number }, width: number, height: number) {
  if (![x,y,rect.left,rect.top,rect.width,rect.height,width,height].every(Number.isFinite) || rect.width <= 0 || rect.height <= 0 || width <= 0 || height <= 0) throw new Error('畫布尺寸無效')
  return { x: Math.max(0,Math.min(width,(x-rect.left)*width/rect.width)), y: Math.max(0,Math.min(height,(y-rect.top)*height/rect.height)) }
}
export function binaryMask(rgba: Uint8ClampedArray, invert = false) {
  if (rgba.length % 4) throw new Error('像素資料長度無效')
  let white = 0
  for (let i=0;i<rgba.length;i+=4) {
    const alpha=rgba[i+3]!/255
    const luma=(rgba[i]!*0.299+rgba[i+1]!*0.587+rgba[i+2]!*0.114)*alpha+255*(1-alpha)
    const value=(Math.round(luma)>=128)!==invert ? 255 : 0
    rgba[i]=value;rgba[i+1]=value;rgba[i+2]=value;rgba[i+3]=255
    if(value) white++
  }
  return white
}

export async function uploadMaskAsset(blob: Blob, name: string, fetcher: typeof fetch = fetch): Promise<ReferenceAsset> {
  if (blob.size > 20 * 1024 * 1024) throw new Error('遮罩不可超過 20 MiB。')
  const response=await fetcher('/api/assets?'+new URLSearchParams({filename:name}),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:blob})
  const value=await response.json()
  if(!response.ok) throw new Error(typeof value.detail==='string'?value.detail:'保存遮罩失敗')
  if(typeof value.id!=='string' || !Number.isInteger(value.width) || !Number.isInteger(value.height)) throw new Error('遮罩保存回應格式不同，未套用。')
  return value as ReferenceAsset
}
