<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ name: string; size?: number }>()
const paths: Record<string, string> = {
  studio: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/>',
  gallery:
    '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M21 16l-5-5-8 9"/>',
  experiments:
    '<rect x="3" y="5" width="7" height="14" rx="1.5"/><rect x="14" y="5" width="7" height="14" rx="1.5"/>',
  assets: '<path d="M4 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2z"/>',
  models: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
  training: '<path d="M4 18l5-6 4 3 7-9"/><path d="M4 21h16"/>',
  system: '<rect x="4" y="4" width="16" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  settings:
    '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>',
}
Object.assign(paths, {
  text: '<path d="M5 6h14M5 12h10M5 18h7"/>',
  redraw: '<path d="M4 11a8 8 0 0114-5l2 2M20 13a8 8 0 01-14 5l-2-2"/>',
  inpaint: '<rect x="3" y="3" width="18" height="18" rx="2" stroke-dasharray="3 3"/>',
  control: '<circle cx="12" cy="5" r="2"/><path d="M12 7v6m-5-3h10m-5 3l-4 8m4-8l4 8"/>',
  reference:
    '<circle cx="12" cy="12" r="9"/><circle cx="9" cy="9" r="1"/><circle cx="15" cy="9" r="1"/>',
  refresh: '<path d="M20 12a8 8 0 11-2.3-5.7M20 4v5h-5"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
})
const markup = computed(() => paths[props.name] || paths.studio)
</script>
<template>
  <svg
    :width="size || 22"
    :height="size || 22"
    viewBox="0 0 24 24"
    aria-hidden="true"
    class="ui-icon"
    v-html="markup"
  ></svg>
</template>
<style scoped>
.ui-icon {
  display: block;
  flex: none;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
