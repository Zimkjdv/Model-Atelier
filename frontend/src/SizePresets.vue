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
</script>
<template>
  <p class="size-presets-label">輸出尺寸</p
  ><div class="size-presets" role="group" aria-label="輸出尺寸比例"
    ><button
      v-for="(size, i) in sizes"
      :key="labels[i]"
      type="button"
      :disabled="disabled"
      :aria-pressed="width === size[0] && height === size[1]"
      @click="emit('select', size[0]!, size[1]!)"
      ><i :style="{ aspectRatio: labels[i]!.replace(':', ' / ') }"></i>{{ labels[i] }}</button
    ></div
  ><p class="size-summary"
    >{{ width }} × {{ height }} 像素 · {{ ((width * height) / 1000000).toFixed(2) }} MP</p
  >
</template>
