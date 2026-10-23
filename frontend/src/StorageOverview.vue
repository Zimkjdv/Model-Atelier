<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from './apiClient'

type Volume = {
  id: string
  path: string
  total: number | null
  free: number | null
  status: string
}
type Directory = {
  id?: string
  role: string
  path: string
  resolved_path: string | null
  volume_id: string | null
  status: string
  error: string | null
  can_open?: boolean
}
type Report = {
  checked_at: string
  warnings: string[]
  volumes: Volume[]
  directories: Directory[]
  folder_open_supported?: boolean
  totals: { total: number | null; free: number | null; volume_count: number; partial: boolean }
}
const report = ref<Report | null>(null)
const busy = ref(false),
  error = ref(''),
  opening = ref<string | null>(null)
const openMessage = ref(''),
  openError = ref('')
let controller: AbortController | null = null,
  alive = true
const gib = (value: number | null) =>
  value === null ? '未知' : `${(value / 1024 ** 3).toFixed(2)} GiB`
const usage = (volume: Volume) =>
  volume.total && volume.free !== null
    ? Math.max(0, Math.min(100, Math.round((1 - volume.free / volume.total) * 100)))
    : null
const groups = computed(() => {
  if (!report.value) return []
  const value = report.value
  const result: { id: string; label: string; volume: Volume | null; entries: Directory[] }[] =
    value.volumes.map((volume) => ({
      id: volume.id,
      label: volume.path,
      volume,
      entries: value.directories.filter((entry) => entry.volume_id === volume.id),
    }))
  const unknown = value.directories.filter((entry) => !entry.volume_id)
  if (unknown.length)
    result.push({ id: 'unknown', label: '其他目錄', volume: null, entries: unknown })
  return result
})

async function refresh() {
  if (busy.value || opening.value) return
  busy.value = true
  error.value = ''
  controller = new AbortController()
  try {
    const value = await api<Report>('storage', 'GET', undefined, controller.signal)
    if (alive) report.value = value
  } catch (e) {
    if (alive)
      error.value =
        '目錄與容量更新失敗。' +
        (report.value ? '目前顯示上次快照。' : '') +
        (e instanceof Error ? e.message : '')
  } finally {
    if (alive) busy.value = false
  }
}

async function openDirectory(entry: Directory) {
  if (opening.value || busy.value || !entry.id || !entry.can_open || !entry.resolved_path) return
  opening.value = entry.id
  openMessage.value = ''
  openError.value = ''
  try {
    const result = await api<{ opened: boolean; directory_id: string }>(
      'storage/open-directory',
      'POST',
      {
        directory_id: entry.id,
        expected_path: entry.resolved_path,
      },
    )
    if (result?.opened !== true || result.directory_id !== entry.id) {
      throw new Error('未收到可確認的開啟回應，請查看檔案總管視窗後再操作。')
    }
    if (alive) openMessage.value = `已要求檔案總管開啟「${entry.role}」。`
  } catch (e) {
    if (alive) openError.value = e instanceof Error ? e.message : '無法開啟資料夾，請稍後重試。'
  } finally {
    if (alive) opening.value = null
  }
}
function openTitle(entry: Directory) {
  if (report.value?.folder_open_supported === undefined) return '請重新啟動平台後使用開啟資料夾功能'
  if (!report.value?.folder_open_supported) return '開啟資料夾僅支援 Windows 本機平台'
  if (!entry.can_open) return entry.error || '此目錄目前無法開啟'
  return `在檔案總管開啟${entry.role}`
}
onMounted(refresh)
onBeforeUnmount(() => {
  alive = false
  controller?.abort()
})
</script>

<template>
  <section class="panel storage-overview" aria-label="目錄與磁碟容量" :aria-busy="busy">
    <div class="storage-heading">
      <div
        ><h2>目錄與磁碟容量</h2
        ><p class="storage-subtitle">資料位置與磁碟使用情況，一目了然。</p></div
      >
      <button
        type="button"
        class="secondary storage-refresh"
        :disabled="busy || opening !== null"
        @click="refresh"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1" />
        </svg>
        {{ busy ? '更新中…' : '更新容量' }}
      </button>
    </div>
    <p v-if="error" class="notice warning storage-feedback" role="alert">{{ error }}</p>
    <p v-if="openError" class="notice warning storage-feedback" role="alert">{{ openError }}</p>
    <p v-if="openMessage" class="notice storage-feedback" role="status">{{ openMessage }}</p>
    <p v-if="!report && busy" class="storage-empty" role="status">正在讀取本機目錄與磁碟容量…</p>
    <template v-if="report">
      <dl class="storage-summary">
        <div
          ><dt>可用空間</dt><dd class="storage-free">{{ gib(report.totals.free) }}</dd></div
        >
        <div
          ><dt>總容量</dt><dd>{{ gib(report.totals.total) }}</dd></div
        >
        <div
          ><dt>可讀磁碟區</dt><dd>{{ report.totals.volume_count }}<span>個</span></dd></div
        >
      </dl>
      <div class="storage-snapshot">
        <span v-if="report.totals.partial" class="storage-partial">部分容量未知</span>
        <span>本機目錄快照 · {{ new Date(report.checked_at).toLocaleString() }}</span>
      </div>
      <div class="storage-volumes">
        <article
          v-for="group in groups"
          :key="group.id"
          class="storage-volume"
          :aria-label="'磁碟區 ' + group.label"
        >
          <div class="storage-volume-heading">
            <span class="storage-drive-icon" aria-hidden="true"
              ><svg viewBox="0 0 24 24">
                <rect x="3" y="5" width="18" height="14" rx="3" />
                <path d="M3 13h18M16 16h.01M18 16h.01" /></svg
            ></span>
            <div class="storage-volume-title"
              ><h3>{{ group.label }}</h3
              ><span>{{ group.entries.length }} 個目錄</span></div
            >
            <span v-if="group.volume && usage(group.volume) !== null" class="storage-usage-label"
              >已使用 {{ usage(group.volume) }}%</span
            >
            <span v-else class="storage-usage-label">容量未知</span>
          </div>
          <template v-if="group.volume">
            <div
              v-if="usage(group.volume) !== null"
              class="storage-meter"
              :class="{ 'storage-low': (usage(group.volume) ?? 0) >= 90 }"
              role="progressbar"
              :aria-label="group.label + ' 已使用容量'"
              aria-valuemin="0"
              aria-valuemax="100"
              :aria-valuenow="usage(group.volume) ?? undefined"
            >
              <span :style="{ width: (usage(group.volume) ?? 0) + '%' }"></span>
            </div>
            <p class="storage-volume-capacity"
              ><span
                >可用 <strong>{{ gib(group.volume.free) }}</strong></span
              ><span>總計 {{ gib(group.volume.total) }}</span></p
            >
          </template>
          <ul class="storage-directories" aria-label="目錄清單">
            <li
              v-for="entry in group.entries"
              :key="entry.id || entry.role + entry.path"
              class="storage-directory"
            >
              <div class="storage-directory-info">
                <h4
                  >{{ entry.role
                  }}<span v-if="entry.status === 'missing'" class="storage-entry-status"
                    >尚未建立</span
                  ></h4
                >
                <code>{{ entry.path }}</code>
                <small v-if="entry.resolved_path && entry.resolved_path !== entry.path"
                  >實際位置：{{ entry.resolved_path }}</small
                >
                <span v-if="entry.error" class="storage-entry-error">{{ entry.error }}</span>
              </div>
              <button
                type="button"
                class="storage-folder"
                :disabled="!entry.can_open || busy || opening !== null"
                :title="openTitle(entry)"
                :aria-label="'開啟' + entry.role + '資料夾'"
                :aria-busy="opening === entry.id"
                @click="openDirectory(entry)"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Zm0 3h18"
                  />
                </svg>
              </button>
            </li>
          </ul>
        </article>
      </div>
      <div class="storage-notes">
        <p v-if="report.folder_open_supported === undefined"
          >請重新啟動平台後使用開啟資料夾功能。</p
        >
        <p v-else-if="!report.folder_open_supported"
          >開啟資料夾僅支援 Windows 本機平台；仍可查看並複製完整路徑。</p
        >
        <p v-for="warning in report.warnings" :key="warning">{{ warning }}</p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.storage-overview {
  margin-top: 20px;
}
.storage-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.storage-heading h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 18px;
}
.storage-subtitle {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 12px;
}
.storage-refresh {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-shrink: 0;
  min-height: 42px;
}
svg {
  display: block;
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.storage-summary {
  display: grid;
  grid-template-columns: 1fr 1fr 0.7fr;
  gap: 16px;
  margin: 22px 0 12px;
  padding: 18px 20px;
  background: #13191b;
  border: 1px solid #303b3e;
  border-radius: 10px;
}
.storage-summary > div {
  min-width: 0;
}
.storage-summary dt {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.storage-summary dd {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.4px;
  font-variant-numeric: tabular-nums;
}
.storage-summary .storage-free {
  color: #b6dba9;
}
.storage-summary dd span {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 400;
  color: var(--text-muted);
}
.storage-snapshot {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 18px;
  color: var(--text-muted);
  font-size: 11px;
}
.storage-partial {
  color: var(--text-warning);
}
.storage-volumes {
  display: grid;
  gap: 14px;
}
.storage-volume {
  min-width: 0;
  border: 1px solid #354047;
  border-radius: 10px;
  overflow: hidden;
  background: #161d20;
}
.storage-volume-heading {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 17px 18px 12px;
}
.storage-drive-icon {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  border-radius: 9px;
  color: #b1c2c9;
  background: #253036;
}
.storage-volume-title {
  min-width: 0;
}
.storage-volume-title h3 {
  margin: 0 0 4px;
  color: var(--text-primary);
  font:
    600 15px 'Cascadia Code',
    Consolas,
    monospace;
  overflow-wrap: anywhere;
}
.storage-volume-title > span {
  color: var(--text-muted);
  font-size: 11px;
}
.storage-usage-label {
  margin-left: auto;
  white-space: nowrap;
  font-size: 11px;
  color: var(--text-muted);
}
.storage-meter {
  height: 6px;
  margin: 0 18px;
  border-radius: 8px;
  background: #303a3e;
  overflow: hidden;
}
.storage-meter > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #83b8c4;
}
.storage-meter.storage-low > span {
  background: #e7b978;
}
.storage-volume-capacity {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 6px 14px;
  margin: 10px 18px 17px;
  font-size: 11px;
  color: var(--text-muted);
}
.storage-volume-capacity strong {
  color: #d7e4df;
  font-weight: 500;
}
.storage-directories {
  list-style: none;
  padding: 0;
  margin: 0;
  border-top: 1px solid #303c41;
}
.storage-directory {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
}
.storage-directory + .storage-directory {
  border-top: 1px solid #2b363b;
}
.storage-directory-info {
  flex: 1;
  min-width: 0;
}
.storage-directory h4 {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 0 0 6px;
  color: #dfe8e5;
  font-size: 13px;
  font-weight: 550;
  line-height: 1.5;
}
.storage-directory code {
  display: block;
  overflow-wrap: anywhere;
  word-break: break-word;
  color: #aebfc7;
  font:
    11px/1.65 'Cascadia Code',
    Consolas,
    monospace;
}
.storage-directory small {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 10px;
  overflow-wrap: anywhere;
}
.storage-entry-status {
  padding: 2px 6px;
  border-radius: 4px;
  background: #30291e;
  color: var(--text-warning);
  font-size: 10px;
  font-weight: 400;
}
.storage-entry-error {
  display: block;
  margin-top: 5px;
  color: var(--text-warning);
  font-size: 11px;
  line-height: 1.6;
}
.storage-folder {
  display: grid;
  place-items: center;
  width: 44px;
  min-height: 44px;
  flex-shrink: 0;
  border: 1px solid #365b69;
  border-radius: 10px;
  background: #172f39;
  color: #8fcbdc;
}
.storage-folder svg {
  width: 22px;
  height: 22px;
}
.storage-folder:hover:not(:disabled) {
  background: #244551;
  border-color: #74b4c9;
  color: #c4edf6;
}
.storage-folder:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}
.storage-folder[aria-busy='true'] {
  cursor: wait;
}
.storage-notes {
  margin-top: 16px;
}
.storage-notes p {
  margin: 5px 0 0;
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.7;
}
.storage-feedback {
  padding: 10px 12px;
  border: 1px solid var(--border-notice);
  border-radius: 7px;
  font-size: 12px;
}
.storage-feedback.warning {
  border-color: var(--border-warning);
}
.storage-empty {
  margin: 22px 0 0;
}
@media (max-width: 600px) {
  .storage-overview {
    padding: 18px 14px;
  }
  .storage-heading {
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 12px;
  }
  .storage-summary {
    grid-template-columns: 1fr 1fr;
    padding: 14px;
    gap: 16px 12px;
  }
  .storage-summary > div:last-child {
    grid-column: 1 / -1;
    display: flex;
    align-items: baseline;
    gap: 12px;
  }
  .storage-summary > div:last-child dt {
    margin: 0;
  }
  .storage-summary dd {
    font-size: 18px;
  }
  .storage-volume-heading {
    padding: 14px 12px 12px;
    gap: 9px;
  }
  .storage-meter {
    margin: 0 12px;
  }
  .storage-volume-capacity {
    margin: 10px 12px 14px;
  }
  .storage-directory {
    padding: 13px 12px;
    gap: 10px;
  }
  .storage-directory code {
    font-size: 10px;
  }
}
</style>
