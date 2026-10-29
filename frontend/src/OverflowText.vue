<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef, useId, watch } from 'vue'

const props = defineProps<{ text: string }>()
const id = useId()
const anchor = ref<HTMLElement | null>(null)
const tooltip = ref<HTMLElement | null>(null)
const visible = ref(false)
const tooltipRoot = shallowRef<HTMLElement | string>('body')
const position = ref({ left: '0px', top: '0px' })
let timer: ReturnType<typeof setTimeout> | undefined
let hovered = false

function hide() {
  clearTimeout(timer)
  visible.value = false
  hovered = false
  tooltip.value?.hidePopover()
}
async function show() {
  clearTimeout(timer)
  const element = anchor.value
  if (!element || element.scrollWidth <= element.clientWidth) return hide()
  visible.value = true
  await nextTick()
  if (!visible.value || !tooltip.value || !element.isConnected) return
  tooltip.value.showPopover()
  place()
}
function place() {
  const element = anchor.value
  if (!element || !tooltip.value || !visible.value) return
  const bounds = element.getBoundingClientRect()
  if (bounds.bottom < 0 || bounds.top > innerHeight) return hide()
  const box = tooltip.value.getBoundingClientRect()
  position.value = {
    left: Math.max(12, Math.min(bounds.left, innerWidth - box.width - 12)) + 'px',
    top:
      (bounds.top >= box.height + 20
        ? bounds.top - box.height - 8
        : Math.min(bounds.bottom + 8, innerHeight - box.height - 12)) + 'px',
  }
}
function scroll() {
  if (!visible.value) return
  if (!hovered && !anchor.value?.matches(':hover') && document.activeElement !== anchor.value)
    hide()
  else place()
}
function leave() {
  clearTimeout(timer)
  timer = setTimeout(() => {
    if (!hovered && document.activeElement !== anchor.value) hide()
  }, 120)
}
function keepTooltip() {
  clearTimeout(timer)
  hovered = true
}
function leaveTooltip() {
  hovered = false
  leave()
}
function dismiss(event: KeyboardEvent) {
  if (event.key === 'Escape' && visible.value) {
    event.preventDefault()
    hide()
  }
}
watch(() => props.text, hide)
onMounted(() => {
  tooltipRoot.value =
    anchor.value?.closest('dialog')?.querySelector<HTMLElement>('[data-overflow-tooltip-root]') ||
    'body'
  window.addEventListener('scroll', scroll, true)
  window.addEventListener('resize', hide)
  window.addEventListener('keydown', dismiss, true)
})
onBeforeUnmount(() => {
  hide()
  window.removeEventListener('scroll', scroll, true)
  window.removeEventListener('resize', hide)
  window.removeEventListener('keydown', dismiss, true)
})
</script>

<template>
  <span
    ref="anchor"
    class="overflow-text"
    tabindex="0"
    :aria-describedby="visible ? id : undefined"
    @mouseenter="show"
    @mouseleave="leave"
    @focus="show"
    @blur="leave"
    >{{ text }}</span
  >
  <Teleport :to="tooltipRoot">
    <span
      :id="id"
      ref="tooltip"
      popover="manual"
      role="tooltip"
      class="overflow-tooltip"
      :style="position"
      @mouseenter="keepTooltip"
      @mouseleave="leaveTooltip"
      >{{ text }}</span
    >
  </Teleport>
</template>

<style scoped>
.overflow-text {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.overflow-tooltip {
  position: fixed;
  inset: auto;
  margin: 0;
  width: max-content;
  max-width: min(420px, calc(100vw - 24px));
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid var(--line2);
  border-radius: 8px;
  background: var(--raised);
  color: var(--ink);
  font:
    500 13px / 1.6 'Microsoft JhengHei',
    system-ui,
    sans-serif;
  overflow-wrap: anywhere;
  white-space: normal;
  box-shadow: 0 8px 24px #0005;
}
</style>
