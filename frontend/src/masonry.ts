import type { ObjectDirective } from 'vue'
const observers = new WeakMap<HTMLElement, { observer: ResizeObserver; cancel: () => void }>()
function mount(el: HTMLElement, enabled: boolean) {
  observers.get(el)?.observer.disconnect()
  observers.get(el)?.cancel()
  let frame = 0
  const arrange = () => {
    frame = 0
    for (const child of Array.from(el.children) as HTMLElement[]) {
      const span = enabled
        ? 'span ' + Math.ceil((child.getBoundingClientRect().height + 16) / 24)
        : ''
      if (child.style.gridRowEnd !== span) child.style.gridRowEnd = span
    }
  }
  const schedule = () => {
    if (!frame) frame = requestAnimationFrame(arrange)
  }
  const observer = new ResizeObserver(schedule)
  observer.observe(el)
  for (const child of Array.from(el.children)) observer.observe(child)
  observers.set(el, { observer, cancel: () => cancelAnimationFrame(frame) })
  schedule()
}
export const vMasonry: ObjectDirective<HTMLElement, boolean> = {
  mounted: (el, binding) => mount(el, binding.value),
  updated: (el, binding) => mount(el, binding.value),
  unmounted: (el) => {
    observers.get(el)?.observer.disconnect()
    observers.get(el)?.cancel()
    observers.delete(el)
  },
}
