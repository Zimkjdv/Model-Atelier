<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
type Memory = { total: number | null; used: number | null; free: number | null }
type System = { host: string; os: string; python: string; updated_at: string; gpus: (Memory & { index: string; name: string; driver: string })[]; gpu_error: string | null; ram: Memory; disk: Memory & { path: string } }
type Engine = { connected: boolean; url: string; error?: string; stats?: { system: { comfyui_version?: string; ram_total?: number; ram_free?: number }; devices: { name: string; vram_total?: number; vram_free?: number }[] } }
const page = ref('系統資訊'), system = ref<System | null>(null), engine = ref<Engine | null>(null)
const url = ref(''), error = ref(''), message = ref(''), busy = ref(false), saving = ref(false)
const pages = ['創作工作台', '模型庫', '作品庫', '系統資訊', '設定']
let timer: ReturnType<typeof setInterval> | undefined
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch('/api/' + path, options)
  if (!response.ok) throw new Error(response.status === 422 ? '位址格式不正確，請使用 HTTP 或 HTTPS 位址。' : `請求失敗 (${response.status})`)
  return response.json()
}
async function refresh() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  const results = await Promise.allSettled([api<System>('system'), api<Engine>('engine')])
  if (results[0].status === 'fulfilled') system.value = results[0].value
  else error.value = '硬體資訊更新失敗。先前資料可能已過期，請確認後端已啟動。'
  if (results[1].status === 'fulfilled') engine.value = results[1].value
  else { engine.value = null; error.value += ' 引擎狀態無法更新。' }
  busy.value = false
}
async function save() {
  saving.value = true; message.value = ''
  try {
    await api('settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ comfy_url: url.value }) })
    message.value = '設定已保存'; await refresh()
  } catch (e) { message.value = e instanceof Error ? e.message : '保存失敗' }
  finally { saving.value = false }
}
const size = (n: number | null | undefined) => n == null ? '無法取得' : `${(n / 1024 ** 3).toFixed(1)} GiB`
const percent = (m: Memory) => m.total && m.used != null ? Math.min(100, Math.max(0, m.used / m.total * 100)) : 0
onMounted(async () => {
  try { url.value = (await api<{ comfy_url: string }>('settings')).comfy_url }
  catch { message.value = '無法載入設定，請確認後端已啟動。' }
  await refresh()
  timer = setInterval(() => { if (document.visibilityState === 'visible') void refresh() }, 15000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="layout">
    <aside>
      <a class="brand" href="#" @click.prevent="page = '系統資訊'"><span class="brand-icon">M</span><span>Model Atelier<small>個人 AI 創作工作台</small></span></a>
      <div class="nav-label">WORKSPACE</div>
      <nav aria-label="主要導覽"><button v-for="(item, i) in pages" :key="item" :class="{ active: page === item }" @click="page = item"><span class="nav-icon">{{ ['◈', '▦', '▧', '◉', '⚙'][i] }}</span>{{ item }}<span v-if="i < 3" class="soon">待開發</span></button></nav>
      <div class="sidebar-footer"><span class="dot" :class="{ online: engine?.connected }"></span>{{ engine?.connected ? 'ComfyUI 已連線' : 'ComfyUI 未連線' }}<small>LOCAL STUDIO · v0.1</small></div>
    </aside>
    <main>
      <header><span>工作空間 <span class="slash">/</span> {{ page }}</span><span class="badge">本地部署</span></header>
      <section class="content">
        <div class="heading"><div><div class="eyebrow">YOUR CREATIVE ENVIRONMENT</div><h1>{{ page }}</h1><p>{{ page === '系統資訊' ? '了解你的創作環境，讓每一次實驗都有跡可循。' : page === '設定' ? '連接模型執行環境，建立你的個人工作空間。' : '從這裡開始，逐步建立你的創作流程。' }}</p></div><button v-if="page === '系統資訊'" class="secondary" :disabled="busy" @click="refresh">{{ busy ? '更新中…' : '↻ 重新整理' }}</button></div>
        <p v-if="error" role="alert" class="notice warning">{{ error }}</p>
        <template v-if="page === '系統資訊'">
          <div class="host-bar"><span class="chip">平台主機</span><strong>{{ system?.host ?? '讀取中' }}</strong><span class="muted">每 15 秒更新 · {{ system ? new Date(system.updated_at).toLocaleTimeString() : '等待資訊' }}</span></div>
          <div class="cards" v-if="system">
            <article class="card gpu" v-for="gpu in system.gpus" :key="gpu.index"><div class="card-label">GPU {{ gpu.index }} <span>NVIDIA</span></div><h2>{{ gpu.name.replace('NVIDIA GeForce ', '') }}</h2><p class="muted">專用顯示記憶體</p><div class="amount">{{ size(gpu.free) }} <small>可用 / {{ size(gpu.total) }}</small></div><div class="meter"><div :style="{ width: percent(gpu) + '%' }"></div></div><footer>已使用 {{ size(gpu.used) }}<span>驅動 {{ gpu.driver }}</span></footer></article>
            <article v-if="system.gpu_error" class="card"><div class="card-label">GPU</div><h2>無法取得</h2><p>{{ system.gpu_error }}</p><p class="muted">其他平台功能仍可使用。</p></article>
            <article class="card"><div class="card-label">SYSTEM MEMORY <span>RAM</span></div><h2>系統記憶體</h2><p class="muted">平台主機可用記憶體</p><div class="amount">{{ size(system.ram.free) }} <small>/ {{ size(system.ram.total) }}</small></div><div class="meter violet"><div :style="{ width: percent(system.ram) + '%' }"></div></div><footer>已使用 {{ size(system.ram.used) }}</footer></article>
            <article class="card"><div class="card-label">STORAGE <span>DISK</span></div><h2>資料儲存空間</h2><p class="muted">平台資料目錄所在磁碟</p><div class="amount">{{ size(system.disk.free) }} <small>/ {{ size(system.disk.total) }}</small></div><div class="meter blue"><div :style="{ width: percent(system.disk) + '%' }"></div></div><footer>已使用 {{ size(system.disk.used) }}</footer></article>
          </div>
          <div v-else class="card">{{ busy ? '正在讀取硬體資訊…' : '尚無硬體資料，請重新整理。' }}</div>
          <article class="panel"><div class="panel-heading"><div><h2>模型執行環境</h2><p class="muted">資訊來自連接的 ComfyUI，與平台主機分開呈現。</p></div><span class="status" :class="{ connected: engine?.connected }">{{ engine?.connected ? '已連線' : '未連線' }}</span></div><template v-if="engine?.connected"><div v-for="device in engine.stats?.devices" :key="device.name" class="device"><strong>{{ device.name }}</strong><span>VRAM 可用 {{ size(device.vram_free) }} / {{ size(device.vram_total) }}</span></div><p class="muted">執行主機 RAM：{{ size(engine.stats?.system.ram_free) }} 可用 · 遠端磁碟：無法取得（此介面未提供）</p></template><div v-else class="empty-engine"><span class="outline-icon">⌁</span><div><strong>連接你的 ComfyUI</strong><p>{{ engine?.error ?? '設定執行引擎後，即可檢查連線與裝置資訊。' }}</p></div><button class="primary" @click="page = '設定'">設定連線 →</button></div><div class="endpoint">{{ engine?.url ?? '尚未取得位址' }}</div></article>
          <article class="panel details" v-if="system"><h2>環境詳細資訊</h2><dl><dt>作業系統</dt><dd>{{ system.os }}</dd><dt>平台 Python</dt><dd>{{ system.python }}</dd><dt>資料目錄</dt><dd>{{ system.disk.path }}</dd></dl></article>
          <p class="footnote">硬體資訊供資源評估使用。平台不依顯卡型號限制存取；模型能否執行仍取決於完整工作流程。</p>
        </template>
        <form v-else-if="page === '設定'" class="panel settings" @submit.prevent="save"><h2>ComfyUI 連線</h2><p class="muted">先啟動 ComfyUI，再填入其服務位址。設定保存在本機資料庫。</p><label for="url">服務位址</label><input id="url" v-model="url" placeholder="http://127.0.0.1:8188" required type="url"><p class="muted">支援本機或你管理的遠端執行主機。</p><button class="primary" :disabled="saving">{{ saving ? '保存中…' : '保存並檢查連線' }}</button><p role="status">{{ message }}</p><p v-if="engine">{{ engine.connected ? 'ComfyUI 連線成功' : engine.error }}</p></form>
        <article v-else class="panel placeholder"><div class="outline-icon">◈</div><h2>{{ page }}尚未實作</h2><p>目前版本已提供系統資訊與 ComfyUI 連線設定。<br>生成、模型登記與作品保存將依開發清單接續實作。</p><button class="secondary" @click="page = '系統資訊'">查看系統資訊</button></article>
      </section>
    </main>
  </div>
</template>
