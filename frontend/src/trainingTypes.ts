export type TrainingImage = {
  id: string
  path: string
  sha256: string
  size_bytes: number
  width: number
  height: number
  group_id: string
  split: 'train' | 'validation' | 'test' | 'excluded'
  exclusion_reason: string
  exposure: string[]
  identity: 'unreviewed' | 'target' | 'other' | 'mixed'
  character_ids: string[]
  caption: {
    content: string
    style_description: string
    status: 'pending' | 'approved' | 'rejected'
    reviewed_by: string
  }
  provenance: {
    attribution: string
    work_id: string
    source_url: string
    training_use: 'unreviewed' | 'recorded' | 'exclude'
    usage_note: string
    reviewed_by: string
  }
}
export type Readiness = {
  data_ready: boolean
  counts: Record<string, number>
  manifest_sha256: string
  issues: { code: string; image_id: string | null; detail?: string }[]
  warnings: { code: string; image_id: string | null }[]
  checked_at?: string
}
export type DatasetReview = {
  id: string
  revision: number
  updated_at: string
  manifest_sha256: string
  source_root: string
  dataset: {
    dataset_id: string
    version: string
    kind: string
    subject_id: string
    trigger: string
    images: TrainingImage[]
  }
  readiness: Readiness
}
export type DatasetSummary = Pick<DatasetReview, 'id' | 'revision' | 'updated_at'> & {
  dataset_id: string
  version: string
  kind: string
  counts: Record<string, number>
  data_ready: boolean
}
export type TrainingExport = {
  request_id: string
  dataset_id: string
  revision: number
  manifest_sha256: string
  status: string
  path: string
  error?: string
  report?: { train_count: number }
}
export const trainingIssue: Record<string, string> = {
  caption_review_required: '內容標註尚未完成審查',
  source_use_record_required: '來源用途尚未記錄',
  target_character_review_required: '角色身分待確認',
  no_final_test_set: '缺少獨立最終評估圖；正式品質比較前請補齊',
  no_development_validation: '缺少開發評估圖',
  no_training_candidates: '沒有訓練候選',
  final_test_previously_exposed: '最終評估圖已有曝光紀錄',
  source_integrity: '原圖完整性檢查失敗',
  multiple_training_variants: '同原作有多張訓練候選',
}
