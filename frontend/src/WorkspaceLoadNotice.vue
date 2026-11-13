<script setup lang="ts">
defineOptions({ inheritAttrs: false })
defineProps<{ error?: Error }>()

function reloadWorkspace() {
  // A new document can fetch the current build after an update invalidates old chunk URLs.
  // The browser still runs the existing beforeunload guards.
  window.location.reload()
}
</script>

<template>
  <div v-if="error" class="notice warning">
    <p role="alert">工作區載入失敗。請重新載入頁面後再試。</p>
    <button type="button" class="secondary" @click="reloadWorkspace">重新載入頁面</button>
  </div>
  <p v-else class="notice" role="status">正在載入工作區…</p>
</template>
