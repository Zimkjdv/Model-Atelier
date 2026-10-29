<script setup lang="ts">
import { onMounted, onBeforeUnmount, computed, nextTick, ref } from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'
import ReferenceComponents from './ReferenceComponents.vue'
import {
  architectureLabel,
  fileHash,
  fileSize,
  safeMetadataUrl,
  metadataTime,
} from './modelMetadata'
import type { ReferenceCatalog } from './adapterSettings'
const props = defineProps<{ view?: string; managed?: boolean }>()
const metadata = ref<InstanceType<typeof ReferenceComponents> | null>(null)
const editorSelected = ref(false)
const library = ref<ReferenceCatalog | null>(null),
  busy = ref(false),
  editing = ref(false),
  error = ref('')
const reads = createRequestScope()
async function load(sync = false) {
  if (busy.value || editing.value || (sync && editorSelected.value)) return
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
const syncDisabled = computed(
  () => busy.value || editing.value || editorSelected.value || !library.value?.engine_url,
)
defineExpose({ sync: () => load(true), syncDisabled, syncing: busy })
</script>
<template>
  <section aria-label="參考元件庫"
    ><div v-if="!props.managed" class="page-intro"
      ><p>畫風／角色參考需要匹配的 adapter 與影像編碼器。</p
      ><button
        class="secondary"
        :disabled="busy || editing || !library?.engine_url"
        @click="load(true)"
        >同步參考元件</button
      ></div
    ><p v-if="error" class="notice warning" role="alert">{{ error }}</p
    ><p v-if="library?.sync_error" class="notice warning" role="alert"
      >{{ library.sync_error }} 此處保留上次清單。</p
    >
    <article v-if="!library && busy" class="panel placeholder" role="status"
      ><h3>正在讀取參考元件…</h3></article
    >
    <article v-else-if="library && !library.components.length" class="panel placeholder"
      ><h3>尚未同步參考元件清單</h3
      ><p>先準備引擎與既有元件，再同步清單。平台不會自動下載模型檔。</p></article
    >
    <div
      v-if="library?.components.length"
      class="model-collection"
      :class="props.view === 'cards' ? 'collection-cards' : 'collection-list'"
    >
      <article
        v-for="item in library?.components"
        :key="item.role + item.name"
        class="panel reference-model-card model-entry"
      >
        <div class="model-entry-info"
          ><h3>{{ item.name }}</h3>
          <p
            >{{ item.role === 'ipadapter' ? 'IP-Adapter' : 'CLIP Vision' }} ·
            {{ architectureLabel(item.architecture) }}</p
          >
          <details class="collection-details"
            ><summary>來源、授權與檔案資訊</summary
            ><dl
              ><dt>版本</dt><dd>{{ item.version || '未知' }}</dd
              ><dt>家族</dt><dd>{{ item.family || '未知' }}</dd
              ><dt>大小</dt><dd>{{ fileSize(item.size_bytes) }}</dd
              ><dt>SHA256</dt><dd>{{ fileHash(item.sha256) }}</dd
              ><dt>來源</dt
              ><dd
                ><a
                  v-if="safeMetadataUrl(item.source_url)"
                  :href="safeMetadataUrl(item.source_url)"
                  target="_blank"
                  rel="noopener"
                  >查看來源</a
                ><span v-else>未知</span></dd
              ><dt>授權</dt
              ><dd
                >{{ item.license_name || '未知' }}
                <a
                  v-if="safeMetadataUrl(item.license_url)"
                  :href="safeMetadataUrl(item.license_url)"
                  target="_blank"
                  rel="noopener"
                  >查看條款</a
                ></dd
              ><dt>更新時間</dt><dd>{{ metadataTime(item.metadata_updated_at) }}</dd></dl
            ><p>{{ item.notes }}</p></details
          ></div
        >
        <div class="model-entry-status"
          ><span
            class="status"
            :class="{ connected: item.listed }"
            title="清單登記狀態；權重與相容性仍需流程預檢"
            >{{ item.listed ? '可使用' : '最近清單未列出' }}</span
          ></div
        >
        <div class="model-entry-action"
          ><button
            class="secondary"
            :disabled="busy || editing"
            @click="metadata?.editComponent(item)"
            >編輯元件資料</button
          ></div
        >
      </article> </div
    ><p class="footnote"
      >同步只會讀取清單，不會下載模型檔。畫風／角色參考需匹配的 adapter
      與影像編碼器；登記不代表權重已驗證。</p
    ><ReferenceComponents
      ref="metadata"
      :managed="props.managed"
      @editing="editorSelected = $event"
      :library="library"
      :engine-url="library?.engine_url || ''"
      :disabled="busy"
      @updated="reloadAfterEdit"
      @busy="editing = $event"
  /></section>
</template>
