<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'
import UiIcon from './UiIcon.vue'

type Deployment = {
  schema_version: 1
  mode: 'local-only' | 'container-local'
  lan_enabled: boolean
  engine: { url: string; role: 'local-engine' | 'external-engine' }
  storage: { path: string }
}
const report = ref<Deployment | null>(null)
const error = ref('')
const busy = ref(false)
const scope = createRequestScope()
async function load() {
  const request = scope.begin()
  busy.value = true
  error.value = ''
  try {
    const value = await apiJson<Deployment>('/api/deployment', { signal: request.signal })
    if (request.isCurrent()) report.value = value
  } catch {
    if (request.isCurrent()) error.value = '無法更新存取模式；若平台尚未重啟，請先重啟平台服務。'
  } finally {
    if (request.isCurrent()) busy.value = false
  }
}
onMounted(load)
onUnmounted(() => scope.dispose())
</script>

<template>
  <article class="panel deployment-status" aria-labelledby="deployment-title" :aria-busy="busy">
    <div class="system-panel-heading"
      ><h2 id="deployment-title">部署與存取</h2
      ><span v-if="report" class="chip">{{
        report.mode === 'container-local' ? '本機容器' : '本機存取'
      }}</span></div
    >
    <p class="system-panel-source">平台與 ComfyUI 分開執行，以下顯示平台的存取範圍與資料位置。</p>
    <p v-if="error" class="notice warning" role="alert"
      >{{ error }}{{ report ? '下方保留上次資料。' : '' }}</p
    >
    <template v-if="report">
      <div class="deployment-access"
        ><UiIcon name="system" :size="22" /><div
          ><strong>未開放區網或公開連線</strong
          ><p>此模式沒有帳號登入，本機使用者與程式皆視為可信。</p></div
        ></div
      >
      <div class="deployment-grid">
        <section class="deployment-card"
          ><h3>平台與資料</h3><p>平台程序讀取硬體資訊，圖片與資料庫保存在平台的檔案系統。</p
          ><div class="system-path-display"
            ><UiIcon name="assets" :size="18" /><code>{{ report.storage.path }}</code></div
          ></section
        >
        <section class="deployment-card"
          ><div class="deployment-engine-heading"
            ><h3>選定引擎</h3
            ><span class="chip">{{
              report.engine.role === 'local-engine' ? '本機引擎' : '外部引擎'
            }}</span></div
          ><code class="deployment-engine-url">{{ report.engine.url }}</code
          ><p>引擎裝置以該引擎回報為準；平台硬體資訊不代表引擎主機。</p></section
        >
      </div>
    </template>
    <p v-else-if="busy" class="empty-state" role="status">正在讀取存取模式…</p>
    <p v-else class="empty-state">尚未取得部署資訊，請更新存取模式後再查看。</p>
    <div class="deployment-actions"
      ><button type="button" class="secondary" :disabled="busy" @click="load"
        ><UiIcon name="refresh" :size="18" />{{ busy ? '讀取中…' : '更新存取模式' }}</button
      ><p>僅重新讀取狀態，不會修改存取設定。</p></div
    >
  </article>
</template>
