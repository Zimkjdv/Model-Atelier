import { controlEdgeWorkflowId } from './controlSettings'
export type ControlEdge = { job_id: string; workflow_id: string; state: 'not_saved'|'saved'|'unavailable'; image_available: boolean; import_allowed: boolean; message: string; sha256?: string; size_bytes?: number; width?: number; height?: number; edge_pixels?: number; total_pixels?: number; saved_at?: string; anchor?: { workflow_sha256: string }; source?: { node_id: string; filename: string; subfolder: string; type: string } }
export function edgeMetadata(value: unknown, jobId: string): ControlEdge {
  const item=value as ControlEdge, uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  if (!item || !uuid.test(jobId) || item.job_id!==jobId || item.workflow_id!==controlEdgeWorkflowId || !['not_saved','saved','unavailable'].includes(item.state) || typeof item.message!=='string' || typeof item.image_available!=='boolean' || typeof item.import_allowed!=='boolean') throw new Error('邊緣來源或狀態不同，未顯示圖片。')
  if (item.image_available!==(item.state==='saved') || (item.state!=='not_saved' && item.import_allowed)) throw new Error('邊緣保存狀態無效。')
  if (item.state!=='not_saved') {
    const hash=/^[0-9a-f]{64}$/
    if (!hash.test(item.sha256 || '') || !hash.test(item.anchor?.workflow_sha256 || '') || !Number.isSafeInteger(item.size_bytes) || item.size_bytes!<=0 || item.size_bytes!>32*1024*1024 || [item.width,item.height,item.edge_pixels,item.total_pixels].some(n=>!Number.isSafeInteger(n)) || item.width!<64 || item.height!<64 || item.width!>8192 || item.height!>8192 || item.total_pixels!==item.width!*item.height! || item.total_pixels!>16000000 || item.edge_pixels!<0 || item.edge_pixels!>item.total_pixels! || item.source?.node_id!=='16' || item.source.type!=='output' || item.source.subfolder!=='model_atelier/'+jobId || !/^canny_[0-9]+_\.png$/.test(item.source.filename) || typeof item.saved_at!=='string') throw new Error('邊緣檔案快照不完整，未顯示圖片。')
  }
  return item
}
