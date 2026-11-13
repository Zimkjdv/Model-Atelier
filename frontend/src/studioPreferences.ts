import { reactive, readonly, ref } from 'vue'

const key = 'atelier-display-preferences-v2'
const legacyKey = 'atelier-studio-display-v1'

type DisplayPreferences = {
  advanced: boolean
  references: boolean
  models: 'list' | 'cards'
  artworks: 'fixed' | 'masonry'
}

const defaults: DisplayPreferences = {
  advanced: false,
  references: false,
  models: 'list',
  artworks: 'fixed',
}
const value = reactive({ ...defaults })
const error = ref('')
let loaded = false

function readPreferences() {
  try {
    const raw = localStorage.getItem(key)
    if (raw === null) {
      const legacy = JSON.parse(localStorage.getItem(legacyKey) || 'null')
      if (typeof legacy?.advanced === 'boolean') value.advanced = legacy.advanced
      if (typeof legacy?.references === 'boolean') value.references = legacy.references
      return
    }

    const saved = JSON.parse(raw)
    if (
      saved?.version !== 2 ||
      typeof saved.advanced !== 'boolean' ||
      typeof saved.references !== 'boolean' ||
      !['list', 'cards'].includes(saved.models) ||
      !['fixed', 'masonry'].includes(saved.artworks)
    )
      throw new Error('Invalid display preferences')
    Object.assign(value, {
      advanced: saved.advanced,
      references: saved.references,
      models: saved.models,
      artworks: saved.artworks,
    })
  } catch {
    error.value = '無法讀取顯示偏好，已使用預設排版。'
  }
}

function persist() {
  try {
    localStorage.setItem(key, JSON.stringify({ version: 2, ...value }))
    error.value = ''
    return true
  } catch {
    error.value = '瀏覽器暫時無法保存顯示偏好，本次開啟期間仍可調整。'
    return false
  }
}

export function useStudioPreferences() {
  if (!loaded) {
    loaded = true
    readPreferences()
  }
  function set<K extends keyof DisplayPreferences>(name: K, next: DisplayPreferences[K]) {
    if (value[name] === next && !error.value) return
    value[name] = next
    persist()
  }
  function toggle(name: 'advanced' | 'references', event: Event) {
    const details = (event.currentTarget as HTMLElement).closest('details')
    if (!details) return
    details.open = !details.open
    set(name, details.open)
  }
  function reset() {
    Object.assign(value, defaults)
    return persist()
  }
  return { value: readonly(value), error: readonly(error), set, toggle, reset }
}
