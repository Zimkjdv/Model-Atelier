<script setup lang="ts">
import { ref, useId } from 'vue'
withDefaults(defineProps<{ drafts?: boolean }>(), { drafts: true })
const bar = ref<HTMLElement | null>(null)
const id = useId()
function reveal(kind: 'tools' | 'validation') {
  const root = bar.value?.closest('.studio-fields-scroll')
  const target =
    kind === 'tools'
      ? root?.querySelector<HTMLDetailsElement>('.studio-tools')
      : root?.querySelector<HTMLDetailsElement>('.studio-validation') ||
        root?.querySelector<HTMLDetailsElement>('.studio-advanced')
  if (!target) return
  if (!target.id) target.id = id + '-' + kind
  let element: HTMLElement | null = target
  while (element) {
    if (element instanceof HTMLDetailsElement) element.open = true
    element = element.parentElement
  }
  target.scrollIntoView({ block: 'start' })
  target.querySelector('summary')?.focus({ preventScroll: true })
}
</script>

<template>
  <div ref="bar" class="studio-utility-bar" role="group" aria-label="創作輔助工具">
    <button type="button" class="secondary" @click="reveal('tools')">{{
      drafts ? '草稿與設定交換' : '來源與流程資訊'
    }}</button>
    <button type="button" class="secondary" @click="reveal('validation')">相容性與實測</button>
  </div>
</template>
