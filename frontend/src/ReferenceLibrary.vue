<script setup lang="ts">
import { onMounted, onBeforeUnmount, nextTick, ref } from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'
import ReferenceComponents from './ReferenceComponents.vue'
import type { ReferenceCatalog } from './adapterSettings'
const library = ref<ReferenceCatalog | null>(null),
  busy = ref(false),
  editing = ref(false),
  error = ref('')
const reads = createRequestScope()
async function load(sync = false) {
  if (busy.value || editing.value) return
  const request = reads.begin()
  busy.value = true
  error.value = ''
  try {
    const value = await apiJson<ReferenceCatalog>('reference-components' + (sync ? '/sync' : ''), {
      method: sync ? 'POST' : 'GET',
      ...(sync
        ? {
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comfy_url: library.value?.engine_url }),
          }
        : {}),
      signal: request.signal,
    })
    if (request.isCurrent()) library.value = value
  } catch (e) {
    if (request.isCurrent()) error.value = e instanceof Error ? e.message : '無法取得參考元件'
  } finally {
    if (request.isCurrent()) busy.value = false
  }
}
async function reloadAfterEdit() {
  await nextTick()
  await load()
}
onMounted(() => load())
onBeforeUnmount(() => reads.dispose())
</script>
<template>
  <section
    ><div class="page-intro"
      ><p>畫風／角色參考需要匹配的 adapter 與影像編碼器。</p
      ><button
        class="secondary"
        :disabled="busy || editing || !library?.engine_url"
        @click="load(true)"
        >同步參考元件</button
      ></div
    ><p v-if="error" class="notice warning" role="alert">{{ error }}</p
    ><ReferenceComponents
      :library="library"
      :engine-url="library?.engine_url || ''"
      :disabled="busy"
      @updated="reloadAfterEdit"
      @busy="editing = $event"
  /></section>
</template>
