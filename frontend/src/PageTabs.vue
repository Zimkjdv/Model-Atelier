<script setup lang="ts">
import { nextTick, ref } from 'vue'
const props = defineProps<{
  id: string
  label: string
  modelValue: string
  items: { id: string; label: string }[]
  vertical?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const list = ref<HTMLElement | null>(null)
async function key(event: KeyboardEvent) {
  const keys = props.vertical
    ? ['ArrowDown', 'ArrowUp', 'Home', 'End']
    : ['ArrowRight', 'ArrowLeft', 'Home', 'End']
  if (!keys.includes(event.key)) return
  event.preventDefault()
  const index = props.items.findIndex((item) => item.id === props.modelValue)
  const next =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? props.items.length - 1
        : (index + (event.key === keys[0] ? 1 : -1) + props.items.length) % props.items.length
  emit('update:modelValue', props.items[next]!.id)
  await nextTick()
  list.value?.querySelector<HTMLButtonElement>('[aria-selected="true"]')?.focus()
}
</script>
<template>
  <div
    ref="list"
    class="page-tabs"
    :class="{ vertical }"
    role="tablist"
    :aria-label="label"
    :aria-orientation="vertical ? 'vertical' : 'horizontal'"
    @keydown="key"
    ><button
      v-for="item in items"
      :id="id + '-tab-' + item.id"
      :key="item.id"
      type="button"
      role="tab"
      :aria-selected="item.id === modelValue"
      :aria-controls="id + '-panel-' + item.id"
      :tabindex="item.id === modelValue ? 0 : -1"
      @click="emit('update:modelValue', item.id)"
      >{{ item.label }}</button
    ></div
  >
</template>
