<script setup lang="ts">
import { computed } from 'vue'
import { outputPresets } from './outputPresets'
const props = defineProps<{ width: number; height: number; family?: string; disabled?: boolean }>()
const emit = defineEmits<{ select: [width: number, height: number] }>()
const sizes = computed(() => {
  const presets = outputPresets(props.family || 'sdxl')
  return presets.length ? presets : outputPresets('sdxl')
})
const labels = ['1:1', '3:4', '4:3', '16:9']
const nearest = computed(() => {
  const ratio = props.width / props.height
  return labels.reduce((best, label) => {
    const number = (value: string) => {
      const [w, h] = value.split(':').map(Number)
      return w! / h!
    }
    return Math.abs(Math.log(ratio / number(label))) < Math.abs(Math.log(ratio / number(best)))
      ? label
      : best
  })
})
</script>
<template>
  <p class="size-presets-label">輸出尺寸</p
  ><div class="size-presets" role="group" aria-label="輸出尺寸比例"
    ><button
      v-for="(size, i) in sizes"
      :key="labels[i]"
      type="button"
      :disabled="disabled"
      :title="size[0] + ' × ' + size[1] + ' 像素'"
      :aria-pressed="width === size[0] && height === size[1]"
      @click="emit('select', size[0]!, size[1]!)"
      ><i aria-hidden="true" :style="{ aspectRatio: labels[i]!.replace(':', ' / ') }"></i
      >{{ labels[i] }}</button
    ></div
  ><p class="size-summary"
    ><span
      >{{ width }} × {{ height }} 像素 · {{ ((width * height) / 1000000).toFixed(2) }} MP ·
      {{ nearest }}</span
    ><small>可在進階設定自訂尺寸。</small></p
  >
</template>
