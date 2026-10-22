import type { SavedExperiment } from './experimentSettings'
export async function checkedExperimentReport(response:Response,record:SavedExperiment):Promise<Blob> {
  const reader=response.body?.getReader();if(!reader) throw new Error('報告沒有內容。')
  const chunks:Uint8Array[]=[];let size=0
  try {while(true) {const {done,value}=await reader.read();if(done) break;size+=value.byteLength;if(size>(response.ok?8*1024*1024:64*1024)) {await reader.cancel();throw new Error('比較報告超過大小上限。')}chunks.push(value)}}finally {reader.releaseLock()}
  const raw=new Uint8Array(size);let offset=0;for(const chunk of chunks) {raw.set(chunk,offset);offset+=chunk.byteLength}
  let value:any;try {value=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw))}catch {throw new Error('比較報告不是完整 UTF-8 JSON。')}
  if(!response.ok) throw new Error(typeof value.detail==='string'?value.detail:'比較報告匯出失敗。')
  const hash=response.headers.get('X-Atelier-SHA256') || ''
  if(response.headers.get('Content-Type')?.split(';')[0]!=='application/json' || !/^[a-f0-9]{64}$/.test(hash) || value?.kind!=='model-atelier-comparison-results' || value.schema_version!==1 || value.source!=='saved-platform-records' || value.plan?.id!==record.id || value.plan?.plan?.plan_sha256!==record.plan.plan_sha256 || !Array.isArray(value.variants) || value.variants.length!==record.plan.variants.length) throw new Error('報告來源、版本或方案不同，未提供下載。')
  const actual=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(v=>v.toString(16).padStart(2,'0')).join('')
  if(actual!==hash) throw new Error('比較報告 SHA256 不符，未提供下載。')
  return new Blob([raw],{type:'application/json'})
}
