import { onBeforeUnmount, onMounted, watch, type Ref } from 'vue'

/** Keep protection active for cached workspaces, including while saving.
 * Browsers decide whether to show a dialog; this never saves or submits.
 */
export function useUnsavedChanges(dirty: Ref<boolean>, saving?: Ref<boolean>) {
  let mounted = false
  const beforeUnload = (event: BeforeUnloadEvent) => {
    if (!dirty.value && !saving?.value) return
    event.preventDefault()
    event.returnValue = ''
  }
  const update = () => {
    if (!mounted) return
    window.removeEventListener('beforeunload', beforeUnload)
    if (dirty.value || saving?.value) window.addEventListener('beforeunload', beforeUnload)
  }
  const stop = watch(() => dirty.value || !!saving?.value, update, { flush: 'sync' })
  onMounted(() => { mounted = true; update() })
  onBeforeUnmount(() => {
    mounted = false
    stop()
    window.removeEventListener('beforeunload', beforeUnload)
  })
}
