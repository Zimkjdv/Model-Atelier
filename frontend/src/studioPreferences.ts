import { reactive, ref } from 'vue'

const KEY = 'atelier-studio-display-v1'
export function useStudioPreferences() {
  const value = reactive({ advanced: false, references: false })
  const error = ref('')
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(KEY) || 'null')
    if (saved && typeof saved === 'object') {
      for (const key of ['advanced', 'references'] as const) {
        const entry = (saved as Record<string, unknown>)[key]
        if (typeof entry === 'boolean') value[key] = entry
      }
    }
  } catch { error.value = '無法讀取顯示偏好；目前使用預設布局，創作參數不受影響。' }
  function toggle(key: keyof typeof value, event: Event) {
    value[key] = (event.target as HTMLDetailsElement).open
    try {
      localStorage.setItem(KEY, JSON.stringify(value))
      error.value = ''
    } catch { error.value = '顯示偏好僅保留於本次頁面，瀏覽器暫時無法保存；草稿仍可保存到平台。' }
  }
  return { value, error, toggle }
}
