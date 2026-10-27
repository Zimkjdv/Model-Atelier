<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ width: number; height: number; family?: string; disabled?: boolean }>()
const emit = defineEmits<{ select: [width: number, height: number] }>()
const sizes = computed(() =>
  props.family === 'sd1'
    ? [
        [512, 512],
        [512, 680],
        [680, 512],
        [768, 432],
      ]
    : props.family === 'flux'
      ? [
          [1024, 1024],
          [768, 1024],
          [1024, 768],
          [1280, 720],
        ]
      : [
          [1024, 1024],
          [864, 1152],
          [1152, 864],
          [1536, 864],
        ],
)
const labels = ['1:1', '3:4', '4:3', '16:9']
</script>
<template>
  <div class="size-presets" role="group" aria-label="輸出尺寸比例"
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
