<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ src?: string; alt: string }>()
const failed = ref(false)
</script>

<template>
  <span class="example-image">
    <img v-if="src && !failed" :src="src" :alt="alt" decoding="async" @error="failed = true" />
    <span v-else class="example-image-error" role="status">範例圖片無法載入。</span>
  </span>
</template>

<style scoped>
.example-image {
  display: block;
  width: 100%;
  aspect-ratio: 1;
  overflow: hidden;
  border-radius: 8px;
  background: var(--bg);
}
.example-image img,
.example-image-error {
  width: 100%;
  height: 100%;
}
.example-image img {
  display: block;
  object-fit: contain;
}
.example-image-error {
  box-sizing: border-box;
  display: grid;
  place-items: center;
  padding: 8px;
  text-align: center;
}
</style>
