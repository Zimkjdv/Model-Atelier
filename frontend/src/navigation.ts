import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'

export const pages = [
  '創作工作台',
  '作品庫',
  '實驗比較',
  '參考素材',
  '模型庫',
  '訓練工作區',
  '系統資訊',
  '設定',
] as const
export type Page = (typeof pages)[number]
export type Mode = 'checkpoint' | 'flux' | 'inpaint' | 'control' | 'reference'
type Route = { page: Page; mode: Mode; job: string }
const paths: Record<Page, string> = {
  創作工作台: 'studio',
  實驗比較: 'experiments',
  模型庫: 'models',
  作品庫: 'gallery',
  系統資訊: 'system',
  設定: 'settings',
  參考素材: 'assets',
  訓練工作區: 'training',
}
const modes: Mode[] = ['checkpoint', 'flux', 'inpaint', 'control', 'reference']
const fallback: Route = { page: '系統資訊', mode: 'checkpoint', job: '' }
export function routeHash(route: Route): string {
  return (
    '#/' +
    paths[route.page] +
    (route.page === '創作工作台' ? '/' + route.mode : '') +
    (route.page === '作品庫' && route.job ? '?job=' + route.job : '')
  )
}
export function parseRoute(hash: string): { route: Route; invalid: boolean } {
  if (!hash) return { route: { ...fallback }, invalid: false }
  const match = /^#\/([a-z]+)(?:\/([a-z]+))?(?:\?job=([0-9a-f-]{36}))?$/.exec(hash)
  const page = match && pages.find((page) => paths[page] === match[1])
  if (
    !match ||
    !page ||
    (page === '創作工作台' ? !modes.includes(match[2] as Mode) || !!match[3] : !!match[2]) ||
    (match[3] &&
      (page !== '作品庫' || !/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(match[3])))
  ) {
    return { route: { ...fallback }, invalid: true }
  }
  return {
    route: { page, mode: (match[2] as Mode) || 'checkpoint', job: match[3] || '' },
    invalid: false,
  }
}

/** URL contains navigation only, never forms, credentials or submission actions. */
export function useNavigation(canLeave: () => boolean) {
  const initial = parseRoute(window.location.hash)
  const route = ref(initial.route),
    notice = ref(initial.invalid ? '無法辨識此網址，已顯示系統資訊。' : '')
  const page = computed(() => route.value.page),
    studioMode = ref<Mode>(route.value.mode)
  const galleryJob = computed(() => route.value.job)
  let index = Number.isSafeInteger(history.state?.atelierNavigation?.index)
    ? history.state.atelierNavigation.index
    : 0
  let committed = routeHash(route.value),
    reverting = false
  function state(hash: string, position: number) {
    return { ...history.state, atelierNavigation: { index: position, hash } }
  }
  history.replaceState(state(committed, index), '', committed)
  async function focusMain() {
    await nextTick()
    document.getElementById('main-content')?.focus()
    document.title = `${page.value} · Model Atelier`
  }
  function apply(next: Route) {
    route.value = next
    if (next.page === '創作工作台') studioMode.value = next.mode
    committed = routeHash(next)
    void focusMain()
  }
  function navigate(next: Page, mode: Mode = studioMode.value, job = ''): boolean {
    const target = { page: next, mode, job: next === '作品庫' ? job : '' }
    const hash = routeHash(target)
    if (hash === committed) return true
    if (next !== page.value && !canLeave()) return false
    notice.value = ''
    history.pushState(state(hash, ++index), '', hash)
    apply(target)
    return true
  }
  function fromHistory() {
    if (reverting) {
      if (location.hash === committed) reverting = false
      return
    }
    if (location.hash === committed) return
    const parsed = parseRoute(location.hash)
    const entry = history.state?.atelierNavigation
    if (parsed.route.page !== page.value && !canLeave()) {
      if (
        entry?.hash === location.hash &&
        Number.isSafeInteger(entry.index) &&
        entry.index !== index
      ) {
        reverting = true
        history.go(index - entry.index)
      } else history.replaceState(state(committed, index), '', committed)
      return
    }
    index =
      entry?.hash === location.hash && Number.isSafeInteger(entry.index) ? entry.index : index + 1
    const next = {
      ...parsed.route,
      mode: parsed.route.page === '創作工作台' ? parsed.route.mode : studioMode.value,
    }
    notice.value = parsed.invalid ? '無法辨識此網址，已顯示系統資訊。' : ''
    history.replaceState(state(routeHash(next), index), '', routeHash(next))
    apply(next)
  }
  onMounted(() => {
    window.addEventListener('popstate', fromHistory)
    window.addEventListener('hashchange', fromHistory)
    void focusMain()
  })
  onUnmounted(() => {
    window.removeEventListener('popstate', fromHistory)
    window.removeEventListener('hashchange', fromHistory)
  })
  return { page, studioMode, galleryJob, notice, navigate, focusMain }
}
