import type { CreationForm } from './creationSettings'
import type { ModelPreset } from './modelProfiles'

// Both collapsed and expanded views use the backend's evidence statement.
// Form comparisons describe the current controls, never infer its subject or quality.
export function presetEvidence(preset: ModelPreset | null | undefined, form: CreationForm) {
  if (!preset) return { summary: '沒有可用的預設驗證資料。', changes: [] as string[] }
  const changes: string[] = []
  if (
    Object.entries(preset.settings).some(
      ([key, value]) => form[key as keyof CreationForm] !== value,
    )
  )
    changes.push('目前取樣參數已修改，不沿用原配置的驗收結論。')
  if (form.loras.some((item) => item.enabled))
    changes.push('目前啟用 LoRA；基底預設的實測不包含此組合。')
  if (form.workflow_mode === 'image2image' || form.reference_ids.length)
    changes.push('目前使用圖片輸入；文生圖預設的實測不包含此流程。')
  changes.push(
    '歷史實測僅適用紀錄中的題材與環境，未判定目前描述、角色或畫風；登記匹配未驗證目前權重檔。',
  )
  return { summary: preset.validation || '沒有可用的預設驗證資料。', changes }
}
