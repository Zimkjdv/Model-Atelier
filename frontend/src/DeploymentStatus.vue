<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'

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
  <article class="panel details" aria-labelledby="deployment-title" :aria-busy="busy">
    <h2 id="deployment-title">部署與存取</h2>
    <p>目前規劃：同一台電腦使用，平台與 ComfyUI 分開執行。</p>
    <p v-if="error" role="alert">{{ error }}{{ report ? '下方保留上次資料。' : '' }}</p>
    <template v-if="report">
      <p
        ><span class="chip">{{ report.mode === 'container-local' ? '本機容器' : '本機存取' }}</span>
        未開放區網或公開連線。</p
      >
      <dl>
        <dt>平台與資料</dt><dd>平台程序讀取硬體資訊，圖片與資料庫保存在平台的檔案系統。</dd>
        <dt>選定引擎</dt
        ><dd
          >{{ report.engine.role === 'local-engine' ? '本機引擎' : '外部引擎' }} ·
          <code>{{ report.engine.url }}</code></dd
        >
      </dl>
      <p class="muted"
        >引擎裝置以該引擎回報為準；平台硬體資訊不代表引擎主機。此模式沒有帳號登入，本機使用者與程式皆視為可信。</p
      >
    </template>
    <p v-else-if="busy" role="status">正在讀取存取模式…</p>
    <button type="button" :disabled="busy" @click="load">{{
      busy ? '讀取中…' : '更新存取模式'
    }}</button>
  </article>
</template>
