<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import PageTabs from './PageTabs.vue'
import UiIcon from './UiIcon.vue'
import EngineEnvironment from './EngineEnvironment.vue'
import StorageOverview from './StorageOverview.vue'
import LocalEnvironmentCheck from './LocalEnvironmentCheck.vue'
import DeploymentStatus from './DeploymentStatus.vue'
import { gb, usedPercent, type HostSystem, type StorageReport } from './systemTypes'
import type { EngineReport } from './environmentTypes'
const props = defineProps<{
  system: HostSystem | null
  engine: EngineReport | null
  selectedUrl: string
  stale: boolean
  busy: boolean
  error: string
}>()
const emit = defineEmits<{ refresh: []; settings: []; paths: [] }>()
const tab = ref('overview'),
  storage = ref<StorageReport | null>(null),
  localStatus = ref('not_checked'),
  storageState = ref({ stale: false, error: '' })
const items = [
  { id: 'overview', label: '總覽' },
  { id: 'host', label: '主機與引擎' },
  { id: 'storage', label: '儲存與目錄' },
  { id: 'installation', label: '安裝與部署' },
]
const hostOs = computed(() => {
  const raw = props.system?.os || '未知'
  const windows = /^Windows-([^-]+)-(.+)$/.exec(raw)
  return windows
    ? { name: 'Windows ' + windows[1], version: windows[2] }
    : { name: raw, version: '' }
})
const total = computed(() => storage.value?.totals.total ?? null)
const free = computed(() => storage.value?.totals.free ?? null)
const used = computed(() =>
  total.value != null && free.value != null ? Math.max(0, total.value - free.value) : null,
)
const percent = computed(() =>
  total.value && used.value != null ? Math.round((used.value / total.value) * 100) : null,
)
const diagnosis = computed(() =>
  props.engine?.url === props.selectedUrl &&
  props.engine?.diagnostics?.matches_selected_engine !== false
    ? props.engine?.diagnostics
    : null,
)
const environment = computed(() =>
  diagnosis.value?.status === 'available' ? diagnosis.value.system : null,
)
const issues = computed(() => {
  const rows: {
    title: string
    description: string
    action: string
    tab?: string
    settings?: boolean
    warning: boolean
  }[] = []
  if (props.stale || props.system?.gpu_error)
    rows.push({
      title: props.stale ? '主機資料已過期' : 'GPU 查詢失敗',
      description: props.error || props.system?.gpu_error || '保留上次快照，不影響其他本機資訊。',
      action: '查看主機',
      tab: 'host',
      warning: true,
    })
  if (props.engine && (!props.engine.connected || diagnosis.value?.status === 'invalid'))
    rows.push({
      title: props.engine.connected ? '引擎回報待確認' : '引擎未連線',
      description: props.engine.error || '生成與訓練需要恢復連線，仍可瀏覽已保存作品。',
      action: '前往設定',
      settings: true,
      warning: true,
    })
  if (storageState.value.stale)
    rows.push({
      title: '儲存資訊更新失敗',
      description: storageState.value.error,
      action: '更新容量',
      tab: 'storage',
      warning: true,
    })
  for (const volume of storage.value?.volumes || [])
    if (volume.total && volume.free != null && volume.free / volume.total <= 0.1)
      rows.push({
        title: volume.path + ' 容量不足',
        description: '可用空間 ' + gb(volume.free) + '；請先整理此磁碟。',
        action: '管理目錄',
        tab: 'storage',
        warning: true,
      })
  if (localStatus.value === 'not_checked' && props.system?.runtime_kind !== 'container')
    rows.push({
      title: '本機 ComfyUI 安裝尚未檢查',
      description: '只讀取環境資訊，不會生成圖片。',
      action: '檢查安裝',
      tab: 'installation',
      warning: false,
    })
  if (localStatus.value === 'unavailable' || localStatus.value === 'timeout')
    rows.push({
      title: '本機安裝需要確認',
      description: '查看檢查結果與原始警告，不影響選定遠端引擎的獨立回報。',
      action: '查看結果',
      tab: 'installation',
      warning: true,
    })
  return rows
})
const warnings = computed(() => issues.value.filter((item) => item.warning).length)
async function select(value: string, focus = false) {
  tab.value = value
  await nextTick()
  if (focus) {
    const el = document.getElementById('system-panel-' + value)
    el?.scrollIntoView({ block: 'start' })
    el?.focus({ preventScroll: true })
  }
}
</script>
<template>
  <div class="system-workspace">
    <div class="page-intro"
      ><p>先看整體是否健康，需要時再展開細節。</p
      ><div
        ><span class="muted">{{
          system ? '更新於 ' + new Date(system.updated_at).toLocaleTimeString() : '等待資料'
        }}</span
        ><button class="primary" :disabled="busy" @click="emit('refresh')"
          ><UiIcon name="refresh" :size="18" />{{ busy ? '更新中…' : '重新整理' }}</button
        ></div
      ></div
    >
    <div class="system-verdict" :class="{ warning: warnings }" role="status"
      ><div
        ><strong>{{
          warnings
            ? warnings + ' 項需要處理'
            : !system || !engine || !storage
              ? '資料待確認'
              : '整體正常'
        }}</strong>
        · {{ issues.length - warnings }} 項尚未檢查</div
      ><button class="text-button" @click="select('overview', true)">查看項目</button></div
    >
    <div class="system-summary-cards">
      <section class="system-card" aria-label="主機"
        ><div class="summary-title"
          ><h2>主機</h2
          ><span class="chip">{{
            stale ? '資料過期' : system ? '已取得回報' : '未偵測'
          }}</span></div
        ><div class="summary-kpi">{{
          system?.gpus[0]?.name.replace('NVIDIA GeForce ', '') ||
          (system?.gpu_error ? 'GPU 未取得' : '平台主機')
        }}</div
        ><template
          v-for="metric in [
            { label: '顯存', value: system?.gpus[0] },
            { label: '記憶體', value: system?.ram },
          ]"
          :key="metric.label"
          ><div class="summary-resource"
            ><div
              ><span>{{ metric.label }}</span
              ><strong
                >{{
                  metric.value ? gb(metric.value.used) + ' / ' + gb(metric.value.total) : '未知'
                }}
                ·
                {{
                  metric.value && usedPercent(metric.value) != null
                    ? Math.round(usedPercent(metric.value)!) + '%'
                    : '未知'
                }}</strong
              ></div
            ><div class="usage-track"
              ><span
                :style="{ width: (metric.value ? usedPercent(metric.value) : 0) + '%' }"
              ></span></div></div></template
        ><button class="summary-link" @click="select('host', true)">查看主機詳情 →</button></section
      >
      <section class="system-card" aria-label="引擎"
        ><div class="summary-title"
          ><h2>引擎</h2
          ><span class="chip" :class="{ warning: engine && !engine.connected }">{{
            engine?.connected ? '已連線' : engine ? '離線' : '未知'
          }}</span></div
        ><div class="summary-kpi">ComfyUI</div
        ><dl class="summary-facts"
          ><div
            ><dt>版本</dt><dd>{{ environment?.comfyui || '未知' }}</dd></div
          ><div
            ><dt>PyTorch</dt><dd>{{ environment?.pytorch || '未知' }}</dd></div
          ></dl
        ><p class="muted endpoint">{{ selectedUrl || '尚未取得引擎位址' }}</p
        ><button class="summary-link" @click="select('host', true)">查看引擎詳情 →</button></section
      >
      <section class="system-card" aria-label="儲存空間"
        ><div class="summary-title"
          ><h2>儲存空間</h2
          ><span class="chip">{{
            storage?.totals.partial
              ? '部分容量未知'
              : percent != null
                ? '剩餘 ' + (100 - percent) + '%'
                : '容量未知'
          }}</span></div
        ><div class="summary-kpi"
          >{{ gb(used) }}
          <small>/ {{ gb(total) }} · {{ percent == null ? '未知' : percent + '%' }}</small></div
        ><div
          class="usage-track"
          role="progressbar"
          :aria-valuenow="percent ?? undefined"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="'已用 ' + gb(used) + '，總量 ' + gb(total)"
          ><span :style="{ width: (percent || 0) + '%' }"></span></div
        ><div class="storage-legend"
          ><div><span>模型</span><strong>尚未統計</strong></div
          ><div><span>作品</span><strong>尚未統計</strong></div
          ><div><span>其他</span><strong>未知</strong></div></div
        ><p class="footnote">分類統計尚無回報；磁碟合計不當作資料夾用量。</p
        ><button class="summary-link" @click="select('storage', true)"
          >查看目錄與磁碟 →</button
        ></section
      >
    </div>
    <PageTabs id="system" v-model="tab" label="系統資訊分類" :items="items" />
    <div
      v-show="tab === 'overview'"
      id="system-panel-overview"
      role="tabpanel"
      aria-labelledby="system-tab-overview"
      tabindex="-1"
      ><section class="panel"
        ><h2>需要注意</h2><p v-if="!issues.length">目前沒有需要處理的項目。</p
        ><div v-for="item in issues" :key="item.title" class="attention-row"
          ><span class="chip" :class="{ warning: item.warning }">{{
            item.warning ? '需處理' : '未檢查'
          }}</span
          ><div
            ><strong>{{ item.title }}</strong
            ><p>{{ item.description }}</p></div
          ><button
            class="secondary"
            @click="item.settings ? emit('settings') : select(item.tab || 'overview', true)"
            >{{ item.action }}</button
          ></div
        ></section
      ><details
        ><summary>資料來源與更新時間</summary
        ><p
          >平台主機：系統查詢與 nvidia-smi，每 15 秒更新。引擎：選定 URL 的 ComfyUI
          回報。儲存：平台目錄快照，手動更新。失敗保留上次快照，未知不顯示為 0。</p
        ></details
      ></div
    >
    <div
      v-show="tab === 'host'"
      id="system-panel-host"
      class="environment-columns"
      role="tabpanel"
      aria-labelledby="system-tab-host"
      tabindex="-1"
      ><section class="panel host-panel" aria-label="平台主機"
        ><div class="host-heading"
          ><h2><UiIcon name="system" :size="22" />平台主機</h2
          ><span class="chip" :class="{ warning: stale }">{{
            stale ? '快照已過期' : system ? '每 15 秒更新' : '等待資料'
          }}</span></div
        ><p class="host-source">資料來源：系統查詢與 nvidia-smi</p
        ><p v-if="error" role="alert" class="notice warning">{{ error }}</p
        ><dl v-if="system" class="environment-facts host-facts"
          ><div
            ><dt>主機名稱</dt><dd>{{ system.host }}</dd></div
          ><div
            ><dt>部署範圍</dt
            ><dd>{{ system.runtime_kind === 'container' ? '容器可見資源' : '原生平台' }}</dd></div
          ><div class="host-fact-wide host-os"
            ><dt>作業系統</dt
            ><dd class="host-os-display" :title="system.os"
              ><strong>{{ hostOs.name }}</strong
              ><span v-if="hostOs.version" class="host-os-version"
                ><span>版本</span><code>{{ hostOs.version }}</code></span
              ></dd
            ></div
          ><div
            ><dt>平台 Python</dt><dd>{{ system.python }}</dd></div
          ><div
            ><dt>可用記憶體</dt><dd>{{ gb(system.ram.free) }}</dd></div
          ><div class="host-fact-wide host-data-path"
            ><dt>資料目錄</dt
            ><dd class="host-path-display"
              ><UiIcon name="assets" :size="18" /><code>{{ system.disk.path }}</code></dd
            ></div
          ></dl
        ><p v-else class="muted host-empty">尚未取得主機資訊，請重新整理後再查看。</p
        ><section
          v-for="(gpu, index) in system?.gpus || []"
          :key="gpu.index"
          class="host-gpu"
          :aria-label="'GPU ' + gpu.index"
          ><div class="host-gpu-heading"
            ><span class="host-gpu-index">GPU {{ gpu.index }}</span
            ><h3>{{ gpu.name }}</h3></div
          ><dl class="host-gpu-facts"
            ><div
              ><dt>可用顯存</dt><dd>{{ gb(gpu.free) }}</dd></div
            ><div
              ><dt>驅動版本</dt><dd>{{ gpu.driver || '未知' }}</dd></div
            ></dl
          ><p v-if="index" class="host-gpu-usage"
            >已用 {{ gb(gpu.used) }} / {{ gb(gpu.total) }} ·
            {{ usedPercent(gpu) == null ? '未知' : Math.round(usedPercent(gpu)!) + '%' }}</p
          ></section
        ><p v-if="system && !system.gpus.length && !system.gpu_error" class="muted host-empty"
          >目前沒有可顯示的 GPU 資訊。</p
        ><p v-if="system?.gpu_error" class="notice warning">{{ system.gpu_error }}</p
        ><p class="footnote host-note"
          >此處 RAM 屬於平台主機，不代表引擎 RAM。{{
            system?.runtime_kind === 'container'
              ? '此處是容器可見的 OS、RAM、掛載磁碟與 GPU，並非 Windows 宿主機完整資訊。'
              : '多張 GPU 分別保留名稱、索引與驅動。'
          }}主機顯存／RAM 已用與總量集中於上方摘要。</p
        ></section
      ><EngineEnvironment
        hide-summary-versions
        :engine="engine"
        :selected-url="selectedUrl"
        @settings="emit('settings')"
    /></div>
    <div
      v-show="tab === 'storage'"
      id="system-panel-storage"
      role="tabpanel"
      aria-labelledby="system-tab-storage"
      tabindex="-1"
      ><StorageOverview
        :refresh-key="system?.updated_at"
        @report="storage = $event"
        @state="storageState = $event"
      /><button class="secondary" @click="emit('paths')">管理額外模型目錄</button></div
    >
    <div
      v-show="tab === 'installation'"
      id="system-panel-installation"
      role="tabpanel"
      aria-labelledby="system-tab-installation"
      tabindex="-1"
      ><LocalEnvironmentCheck
        v-if="system?.runtime_kind !== 'container'"
        @status="localStatus = $event" /><article v-else class="panel"
        ><h2>本機 ComfyUI 安裝</h2
        ><p
          >容器無法檢查 Windows 的原生 Python 安裝；請在 Windows
          平台執行本機安裝檢查。選定引擎的回報仍獨立可用。</p
        ></article
      ><DeploymentStatus
    /></div>
  </div>
</template>
