<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import ModelLibrary from './ModelLibrary.vue'
import CreationStudio from './CreationStudio.vue'
import FluxStudio from './FluxStudio.vue'
import { fluxWorkflowId } from './fluxSettings'
import AssetLibrary from './AssetLibrary.vue'
import ArtworkLibrary from './ArtworkLibrary.vue'
import LocalModelPaths from './LocalModelPaths.vue'
import EngineEnvironment from './EngineEnvironment.vue'
import LocalEnvironmentCheck from './LocalEnvironmentCheck.vue'
import StorageOverview from './StorageOverview.vue'
import type { EngineReport } from './environmentTypes'
type Memory = { total: number | null; used: number | null; free: number | null }
type System = { host: string; os: string; python: string; updated_at: string; gpus: (Memory & { index: string; name: string; driver: string })[]; gpu_error: string | null; ram: Memory; disk: Memory & { path: string } }
const page = ref('系統資訊'), system = ref<System | null>(null), engine = ref<EngineReport | null>(null)
const artworkNotesDirty = ref(false)
function navigate(next: string) {
  if (next === page.value) return
  if (page.value === '作品庫' && artworkNotesDirty.value && !window.confirm('作品筆記尚未保存或正在保存，確定離開作品庫？')) return
  page.value = next
}
const systemStale = ref(false), savedUrl = ref('')
const galleryJob = ref('')
const restoreRequest = ref<{ artworkId: string; token: number } | null>(null)
const fluxRestoreRequest = ref<{ artworkId: string; token: number } | null>(null)
const studioMode = ref<'checkpoint' | 'flux'>('checkpoint')
let restoreToken = 0
function restoreArtwork(artworkId: string, workflowId?: string | null) {
  const value = { artworkId, token: ++restoreToken }
  if (workflowId === fluxWorkflowId) { studioMode.value = 'flux'; fluxRestoreRequest.value = value }
  else { studioMode.value = 'checkpoint'; restoreRequest.value = value }
  page.value = '創作工作台'
}
const url = ref(''), error = ref(''), message = ref(''), busy = ref(false), saving = ref(false)
const pages = ['創作工作台', '模型庫', '作品庫', '系統資訊', '設定', '參考素材']
let timer: ReturnType<typeof setInterval> | undefined
let alive = true, refreshToken = 0, settingsEpoch = 0, refreshAbort: AbortController | null = null
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch('/api/' + path, options)
  if (!response.ok) throw new Error(response.status === 422 ? '位址格式不正確，請使用 HTTP 或 HTTPS 位址。' : `請求失敗 (${response.status})`)
  return response.json()
}
async function refresh(force = false) {
  if (!alive || (!force && (busy.value || saving.value))) return
  const token = ++refreshToken
  refreshAbort?.abort()
  const controller = new AbortController()
  refreshAbort = controller
  const expectedUrl = savedUrl.value
  busy.value = true
  error.value = ''
  const results = await Promise.allSettled([api<System>('system', { signal: controller.signal }), api<EngineReport>('engine', { signal: controller.signal })])
  if (!alive || token !== refreshToken) return
  if (results[0].status === 'fulfilled') system.value = results[0].value
  systemStale.value = results[0].status !== 'fulfilled'
  if (systemStale.value) error.value = '平台硬體資訊更新失敗，下方保留的舊資料可能已過期。'
  if (results[1].status === 'fulfilled') {
    const incoming = results[1].value
    if (incoming.diagnostics?.matches_selected_engine === false) {
      const reason = '引擎設定已在其他視窗變更，請重新確認連線設定。'
      engine.value = { ...incoming, connected: false, error: reason }
      error.value += ' ' + reason
    } else if (expectedUrl && incoming.url !== expectedUrl) {
      engine.value = null; error.value += ' 引擎回報位址與已保存設定不同，請重新確認連線設定。'
    } else {
      engine.value = incoming
      if (!savedUrl.value) { savedUrl.value = incoming.url; if (!url.value) url.value = incoming.url }
    }
  }
  else { engine.value = null; error.value += ' 引擎狀態無法更新。' }
  busy.value = false; refreshAbort = null
}
async function save() {
  if (saving.value || !alive) return
  ++settingsEpoch; ++refreshToken; refreshAbort?.abort(); refreshAbort = null
  engine.value = null; busy.value = false
  saving.value = true; message.value = ''
  try {
    const value = await api<{ comfy_url: string }>('settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ comfy_url: url.value }) })
    if (!alive) return
    savedUrl.value = value.comfy_url; url.value = value.comfy_url
    message.value = '設定已保存'; await refresh(true)
  } catch (e) { if (alive) { message.value = e instanceof Error ? e.message : '保存失敗'; await refresh(true) } }
  finally { if (alive) saving.value = false }
}
const size = (n: number | null | undefined) => n == null ? '無法取得' : `${(n / 1024 ** 3).toFixed(1)} GiB`
const percent = (m: Memory) => m.total && m.used != null ? Math.min(100, Math.max(0, m.used / m.total * 100)) : 0
onMounted(async () => {
  const epoch = settingsEpoch
  try {
    const value = await api<{ comfy_url: string }>('settings')
    if (alive && epoch === settingsEpoch) { savedUrl.value = value.comfy_url; if (!url.value) url.value = value.comfy_url }
  }
  catch { if (alive && epoch === settingsEpoch) message.value = '無法載入設定，請確認後端已啟動。' }
  if (!alive) return
  await refresh()
  if (!alive) return
  timer = setInterval(() => { if (document.visibilityState === 'visible') void refresh() }, 15000)
})
onUnmounted(() => { alive = false; ++refreshToken; ++settingsEpoch; refreshAbort?.abort(); clearInterval(timer) })
</script>

<template>
  <div class="layout">
    <a class="skip-link" href="#main-content">跳至主要內容</a>
    <aside>
      <a class="brand" href="#" @click.prevent="navigate('系統資訊')"><span class="brand-icon">M</span><span>Model Atelier<small>個人 AI 創作工作台</small></span></a>
      <div class="nav-label">WORKSPACE</div>
      <nav aria-label="主要導覽"><button v-for="(item, i) in pages" :key="item" :class="{ active: page === item }" :aria-label="item" :aria-current="page === item ? 'page' : undefined" :title="item" @click="navigate(item)"><span class="nav-icon" aria-hidden="true">{{ ['◈', '▦', '▧', '◉', '⚙', '▨'][i] }}</span>{{ item }}</button></nav>
      <div class="sidebar-footer"><span class="dot" :class="{ online: engine?.connected }"></span>{{ engine?.connected ? 'ComfyUI 已連線' : 'ComfyUI 未連線' }}<small>LOCAL STUDIO · v0.1</small></div>
    </aside>
    <main id="main-content" tabindex="-1">
      <header><span>工作空間 <span class="slash">/</span> {{ page }}</span><span class="badge">本地部署</span></header>
      <section class="content">
        <div class="heading"><div><div class="eyebrow">YOUR CREATIVE ENVIRONMENT</div><h1>{{ page }}</h1><p>{{ page === '系統資訊' ? '了解你的創作環境，讓每一次實驗都有跡可循。' : page === '設定' ? '連接模型執行環境，建立你的個人工作空間。' : '從這裡開始，逐步建立你的創作流程。' }}</p></div><button v-if="page === '系統資訊'" class="secondary" :disabled="busy" @click="refresh()">{{ busy ? '更新中…' : '↻ 重新整理' }}</button></div>
        <p v-if="error && page === '系統資訊'" role="alert" class="notice warning">{{ error }}</p>
        <div v-if="page === '創作工作台'" class="workflow-switch" role="group" aria-label="創作工作流程"><button class="secondary" :aria-pressed="studioMode === 'checkpoint'" @click="studioMode = 'checkpoint'">Checkpoint／SDXL</button> <button class="secondary" :aria-pressed="studioMode === 'flux'" @click="studioMode = 'flux'">FLUX.1 [schnell]</button><p class="footnote">切換保留各自表單與待確認請求；離開頁面前請保存草稿。</p></div>
        <KeepAlive><CreationStudio v-if="page === '創作工作台' && studioMode === 'checkpoint'" :restore-request="restoreRequest" @models="page = '模型庫'" @assets="page = '參考素材'" @gallery="galleryJob = $event; page = '作品庫'" /><FluxStudio v-else-if="page === '創作工作台' && studioMode === 'flux'" :restore-request="fluxRestoreRequest" @models="page = '模型庫'" @gallery="galleryJob = $event; page = '作品庫'" /></KeepAlive>
        <template v-if="page === '系統資訊'">
          <div class="host-bar"><span class="chip">平台主機</span><strong>{{ system?.host ?? '讀取中' }}</strong><span class="muted">{{ systemStale ? '上次資料 · 本次更新失敗' : '每 15 秒更新' }} · {{ system ? new Date(system.updated_at).toLocaleTimeString() : '等待資訊' }}</span></div>
          <p class="footnote">此區來源為平台主機：RAM／磁碟由本機系統查詢，GPU／驅動由 nvidia-smi 回報；與下方選定引擎的環境分開。</p>
          <div class="cards" v-if="system">
            <article class="card gpu" v-for="gpu in system.gpus" :key="gpu.index"><div class="card-label">GPU {{ gpu.index }} <span>NVIDIA</span></div><h2>{{ gpu.name.replace('NVIDIA GeForce ', '') }}</h2><p class="muted">專用顯示記憶體</p><div class="amount">{{ size(gpu.free) }} <small>可用 / {{ size(gpu.total) }}</small></div><div class="meter"><div :style="{ width: percent(gpu) + '%' }"></div></div><footer>已使用 {{ size(gpu.used) }}<span>驅動 {{ gpu.driver }}</span></footer></article>
            <article v-if="system.gpu_error" class="card"><div class="card-label">GPU</div><h2>無法取得</h2><p>{{ system.gpu_error }}</p><p class="muted">其他平台功能仍可使用。</p></article>
            <article class="card"><div class="card-label">SYSTEM MEMORY <span>RAM</span></div><h2>系統記憶體</h2><p class="muted">平台主機可用記憶體</p><div class="amount">{{ size(system.ram.free) }} <small>/ {{ size(system.ram.total) }}</small></div><div class="meter violet"><div :style="{ width: percent(system.ram) + '%' }"></div></div><footer>已使用 {{ size(system.ram.used) }}</footer></article>
            <article class="card"><div class="card-label">STORAGE <span>DISK</span></div><h2>資料儲存空間</h2><p class="muted">平台資料目錄所在磁碟</p><div class="amount">{{ size(system.disk.free) }} <small>/ {{ size(system.disk.total) }}</small></div><div class="meter blue"><div :style="{ width: percent(system.disk) + '%' }"></div></div><footer>已使用 {{ size(system.disk.used) }}</footer></article>
          </div>
          <div v-else class="card">{{ busy ? '正在讀取硬體資訊…' : '尚無硬體資料，請重新整理。' }}</div>
          <EngineEnvironment :engine="engine" :selected-url="savedUrl" @settings="page = '設定'"/>
          <LocalEnvironmentCheck/>
          <StorageOverview/>
          <article class="panel details" v-if="system"><h2>環境詳細資訊</h2><dl><dt>作業系統</dt><dd>{{ system.os }}</dd><dt>平台 Python</dt><dd>{{ system.python }}</dd><dt>資料目錄</dt><dd>{{ system.disk.path }}</dd></dl></article>
          <p class="footnote">硬體資訊供資源評估使用。平台不依顯卡型號限制存取；模型能否執行仍取決於完整工作流程。</p>
        </template>
        <template v-else-if="page === '設定'"><form class="panel settings" @submit.prevent="save"><h2>ComfyUI 連線</h2><p class="muted">先啟動 ComfyUI，再填入其服務位址。設定保存在本機資料庫。</p><label for="url">服務位址</label><input id="url" v-model="url" :disabled="saving" placeholder="http://127.0.0.1:8188" required type="url"><p class="muted">支援本機或你管理的遠端執行主機。</p><button class="primary" :disabled="saving">{{ saving ? '保存中…' : '保存並檢查連線' }}</button><p role="status">{{ message }}</p><p v-if="engine">{{ engine.connected ? 'ComfyUI 連線成功' : engine.error }}</p></form><LocalModelPaths :selected-engine-url="savedUrl"/></template>
        <ModelLibrary v-else-if="page === '模型庫'" @settings="page = '設定'" />
        <AssetLibrary v-else-if="page === '參考素材'" />
        <ArtworkLibrary v-else-if="page === '作品庫'" :job-id="galleryJob" @studio="navigate('創作工作台')" @restore="restoreArtwork" @dirty="artworkNotesDirty = $event" />
      </section>
    </main>
  </div>
</template>
