import type { ControlForm } from './controlSettings'
import type { ReferenceAsset } from './referenceSettings'
export const cannyPreviewMethod='comfy-kornia-canny-cpu-v1'
const nativeHash='5efd352d92d7749b7b9734a1676fee18f4431d44a8e9477822a7a8f38ad26051'
const sha=(v:unknown):v is string=>typeof v==='string' && /^[0-9a-f]{64}$/.test(v)
export function cannyPreviewInput(form:ControlForm) {
  return {image_asset_id:form.image_asset_id,reference_resize:form.reference_resize,width:form.width,height:form.height,canny_low:form.canny_low,canny_high:form.canny_high}
}
export function cannyPreviewIdentity(form:ControlForm,source?:ReferenceAsset) {
  return JSON.stringify([cannyPreviewInput(form),source?.id,source?.sha256,source?.archived,source?.width,source?.height])
}
export function cannyPreviewProblem(form:ControlForm,source?:ReferenceAsset) {
  if(!source || source.id!==form.image_asset_id || source.archived) return '請選擇一張可用的已保存原圖。'
  if(!sha(source.sha256)) return '素材 SHA256 尚未確認，請更新素材清單。'
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(source.id)) return '素材 ID 不完整。'
  if(!['fit','stretch'].includes(form.reference_resize)) return '請選擇等比補白或拉伸。'
  if([form.width,form.height].some(v=>!Number.isInteger(v) || v<64 || v>8192 || v%8!==0)) return '寬高需為 64–8192，且為 8 的倍數。'
  if(form.width*form.height>1_048_576) return 'CPU 預覽最多 1,048,576 像素；仍可使用原生成尺寸上限。'
  if([form.canny_low,form.canny_high].some(v=>typeof v!=='number' || !Number.isFinite(v)) || form.canny_low<.01 || form.canny_high>.99 || form.canny_low>=form.canny_high) return 'Canny 閾值需符合 0.01 ≤ 低 < 高 ≤ 0.99。'
  return ''
}
async function bytes(response:Response,limit:number) {
  const reader=response.body?.getReader();if(!reader) throw new Error('預覽回應沒有內容。')
  const chunks:Uint8Array[]=[];let size=0
  try {while(true) {const {done,value}=await reader.read();if(done) break;size+=value.byteLength;if(size>limit) {await reader.cancel();throw new Error('預覽回應超過大小上限。')} chunks.push(value)}}
  finally {reader.releaseLock()}
  const raw=new Uint8Array(size);let offset=0;for(const chunk of chunks) {raw.set(chunk,offset);offset+=chunk.byteLength}return raw
}
export type CannyPreviewInfo={method:string;torch:string;kornia:string;pillow:string;native_sha256:string;input_sha256:string;sha256:string}
export async function checkedCannyPreview(response:Response,form:ControlForm,source:ReferenceAsset):Promise<{blob:Blob;info:CannyPreviewInfo}> {
  if(!response.ok) {const raw=await bytes(response,64*1024);let detail='CPU Canny 預覽失敗。';try {const v=JSON.parse(new TextDecoder().decode(raw));if(typeof v.detail==='string') detail=v.detail}catch{} throw new Error(detail)}
  const hash=response.headers.get('X-Atelier-SHA256') || '',encoded=response.headers.get('X-Atelier-Canny-Provenance') || ''
  if(response.headers.get('Content-Type')?.split(';')[0]!=='image/png' || !sha(hash) || response.headers.get('X-Atelier-Width')!==String(form.width) || response.headers.get('X-Atelier-Height')!==String(form.height) || encoded.length>8192 || !/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)) throw new Error('預覽回應與本次輸入不同，未顯示。')
  let info:any
  try {info=JSON.parse(atob(encoded))}catch {throw new Error('預覽來源格式不完整。')}
  const prep=info?.preprocessing
  if(!info || info.method!==cannyPreviewMethod || info.device!=='cpu' || info.dtype!=='float32' || info.native_sha256!==nativeHash || info.image_asset_id!==source.id || !sha(source.sha256) || info.asset_sha256!==source.sha256 || info.sha256!==hash || !sha(info.input_sha256) || info.width!==form.width || info.height!==form.height || info.canny_low!==form.canny_low || info.canny_high!==form.canny_high || info.reference_resize!==form.reference_resize || !prep || prep.id!=='checkpoint-image-input' || prep.version!==1 || prep.sha256!==info.input_sha256 || prep.width!==form.width || prep.height!==form.height || prep.resize!==form.reference_resize || prep.resampling!=='LANCZOS' || prep.background!=='#ffffff' || prep.output_mode!=='RGB' || prep.output_format!=='PNG' || typeof prep.library_version!=='string' || ['torch','kornia','pillow'].some(k=>typeof info[k]!=='string' || !/^[\x20-\x7e]{1,99}$/.test(info[k]))) throw new Error('預覽來源、版本或參數不同，未顯示。')
  const raw=await bytes(response,16*1024*1024),view=new DataView(raw.buffer)
  if(raw.length<33 || [137,80,78,71,13,10,26,10].some((v,i)=>raw[i]!==v) || String.fromCharCode(...raw.slice(12,16))!=='IHDR' || view.getUint32(16)!==form.width || view.getUint32(20)!==form.height || raw[24]!==8 || raw[25]!==2) throw new Error('預覽 PNG 尺寸或格式不同。')
  const actual=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(v=>v.toString(16).padStart(2,'0')).join('')
  if(actual!==hash) throw new Error('預覽圖片 SHA256 不符，未顯示。')
  return {blob:new Blob([raw],{type:'image/png'}),info}
}
