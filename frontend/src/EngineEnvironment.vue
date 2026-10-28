<script setup lang="ts">
import { computed } from 'vue'
import EnvironmentDevices from './EnvironmentDevices.vue'
import {
  cudaStatus,
  environmentSize,
  environmentText,
  environmentTime,
  executionDeviceLabel,
} from './environmentTypes'
import type { EngineReport, EnvironmentMemory } from './environmentTypes'
const props = defineProps<{
  engine: EngineReport | null
  selectedUrl: string
  hideSummaryVersions?: boolean
}>()
const emit = defineEmits<{ settings: [] }>()
const current = computed(() =>
  props.engine && (!props.selectedUrl || props.engine.url === props.selectedUrl)
    ? props.engine
    : null,
)
const diagnostics = computed(() => current.value?.diagnostics ?? null)
const executionDevice = computed(() => {
  const value = current.value?.execution_device
  return value?.engine_url === props.selectedUrl &&
    diagnostics.value?.matches_selected_engine !== false
    ? value
    : null
})
const available = computed(
  () =>
    current.value?.connected &&
    diagnostics.value?.status === 'available' &&
    diagnostics.value.matches_selected_engine !== false,
)
const system = computed(() => (available.value ? diagnostics.value?.system : null))
const statusLabel = computed(() =>
  available.value
    ? '已連線'
    : diagnostics.value?.status === 'invalid'
      ? '回報資料無效'
      : current.value?.connected
        ? '回報待確認'
        : '未連線',
)
const checkedTime = computed(() => {
  if (!diagnostics.value?.checked_at) return '尚未查詢'
  const date = new Date(diagnostics.value.checked_at)
  return Number.isNaN(date.getTime())
    ? '時間未知'
    : date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', hour12: false })
})
const pythonVersion = computed(() => {
  const value = environmentText(system.value?.python)
  return /^\d+\.\d+\.\d+(?:[a-z]+\d+)?/i.exec(value)?.[0] || value
})
function memoryPercent(memory: EnvironmentMemory) {
  return memory.total != null &&
    Number.isFinite(memory.total) &&
    memory.total > 0 &&
    memory.used != null &&
    Number.isFinite(memory.used) &&
    memory.used >= 0 &&
    memory.used <= memory.total
    ? Math.round((memory.used / memory.total) * 100)
    : null
}
const resources = computed(() => {
  if (!available.value || !diagnostics.value) return []
  return [
    ...diagnostics.value.devices.map((device, index) => ({
      key: 'device-' + index,
      label:
        '引擎裝置 ' +
        (device.index ?? '未知') +
        ' · ' +
        (device.type === 'cpu' ? '記憶體' : '顯存'),
      name: environmentText(device.name),
      memory: device.vram,
    })),
    { key: 'ram', label: '引擎記憶體', name: '引擎主機 RAM', memory: diagnostics.value.ram },
  ].map((resource) => ({ ...resource, percent: memoryPercent(resource.memory) }))
})
</script>

<template>
  <article class="panel engine-environment" aria-label="選定引擎的執行環境">
    <div class="engine-heading"
      ><h2>選定引擎</h2
      ><span class="status" :class="{ connected: available }">{{ statusLabel }}</span></div
    >
    <p class="engine-source">資料來源：引擎回報 · 更新於 {{ checkedTime }}</p>
    <div class="environment-endpoint"
      ><code>{{ current?.url || selectedUrl || '尚未取得引擎位址' }}</code
      ><span>ComfyUI /system_stats</span></div
    >
    <p v-if="!available" class="notice warning engine-warning" role="status">{{
      current?.error ||
      (diagnostics?.matches_selected_engine === false
        ? '回報來源與目前選定引擎不符，請確認連線設定後重新整理。'
        : diagnostics?.status === 'invalid'
          ? '引擎回報資料不完整，環境欄位目前未知。'
          : current?.connected
            ? '已連接服務，尚未取得可用的環境診斷資料。'
            : '請確認服務已啟動且位址正確。')
    }}</p>
    <dl class="environment-versions engine-facts">
      <div v-if="!hideSummaryVersions"
        ><dt>ComfyUI</dt><dd>{{ environmentText(system?.comfyui) }}</dd></div
      >
      <div
        ><dt>Python</dt><dd :title="environmentText(system?.python)">{{ pythonVersion }}</dd></div
      >
      <div v-if="!hideSummaryVersions"
        ><dt>PyTorch</dt><dd>{{ environmentText(system?.pytorch) }}</dd></div
      >
      <div
        ><dt>CUDA 版本</dt><dd>{{ environmentText(system?.cuda_runtime) }}</dd></div
      >
      <div
        ><dt>CUDA 可用</dt><dd>{{ cudaStatus(system?.cuda_available) }}</dd></div
      >
      <div
        ><dt>驅動</dt><dd>{{ environmentText(system?.driver) }}</dd></div
      >
      <div
        ><dt>作業系統</dt><dd>{{ environmentText(system?.os) }}</dd></div
      >
      <div
        ><dt>裝置類型／索引</dt
        ><dd
          >{{ executionDevice?.device?.type || '未知'
          }}<template v-if="executionDevice?.device?.index != null">
            / {{ executionDevice.device.index }}</template
          ></dd
        ></div
      >
    </dl>
    <div v-for="resource in resources" :key="resource.key" class="engine-resource">
      <div class="engine-resource-heading"
        ><span :title="resource.name">{{ resource.label }}</span
        ><strong
          >{{ environmentSize(resource.memory.used) }} /
          {{ environmentSize(resource.memory.total) }} ·
          {{ resource.percent == null ? '未知' : resource.percent + '%' }}</strong
        ></div
      >
      <div
        v-if="resource.percent != null"
        class="usage-track"
        role="progressbar"
        :aria-label="resource.label + ' · ' + resource.name"
        :aria-valuenow="resource.percent"
        aria-valuemin="0"
        aria-valuemax="100"
        ><span :style="{ width: resource.percent + '%' }"></span
      ></div>
      <p v-else class="engine-usage-unknown">用量尚無有效回報</p>
    </div>
    <div
      class="engine-device-status"
      :class="{
        'notice warning': executionDevice?.status === 'unavailable',
        'is-available': executionDevice?.status === 'available',
      }"
      role="status"
    >
      <strong>{{ executionDeviceLabel(executionDevice) }}</strong>
      <p v-if="executionDevice?.status === 'unavailable'"
        >原引擎明確回報目前設定的裝置無法使用，新的生成會在提交前停止；草稿、素材及已匯入作品仍可使用。修復後請重新整理，再明確建立新任務。</p
      >
      <p v-else-if="executionDevice?.status !== 'available'"
        >尚未取得有效的即時裝置回報，新的生成仍會檢查模型、元件與節點。</p
      >
    </div>
    <p class="engine-note"
      ><template v-if="hideSummaryVersions">ComfyUI 與 PyTorch 版本集中於上方摘要。</template>CPU
      也是有效裝置；取得裝置不保證模型可載入或顯存足夠。</p
    >
    <details class="engine-memory-details">
      <summary>Torch 記憶體與裝置細節</summary>
      <EnvironmentDevices
        v-if="available && diagnostics?.devices.length"
        :devices="diagnostics.devices"
        memory-label="引擎回報 VRAM"
      />
      <p v-else class="footnote">引擎尚未回報可辨識的裝置資料。</p>
      <dl class="engine-detail-facts"
        ><dt>Python 完整版本</dt
        ><dd
          ><code>{{ environmentText(system?.python) }}</code></dd
        ><dt>引擎 RAM 可用</dt
        ><dd>{{ environmentSize(available ? diagnostics?.ram.free : null) }}</dd></dl
      >
      <p class="footnote"
        >未知欄位表示此引擎未提供有效資料。裝置是引擎回報，不能證明每項任務實際使用哪張
        GPU；回報的可用 VRAM 可能包含可回收快取，與平台 nvidia-smi 數值可能不同。</p
      >
    </details>
    <details
      class="engine-diagnostics"
      :open="!available || executionDevice?.status === 'unavailable'"
    >
      <summary
        >回報來源、裝置狀態與異常說明<span
          v-if="diagnostics?.warnings.length"
          class="engine-detail-count"
          >{{ diagnostics.warnings.length }} 項說明</span
        ></summary
      >
      <dl class="engine-detail-facts"
        ><dt>診斷來源</dt><dd>{{ diagnostics?.source || '未知' }}</dd
        ><dt>查詢時間</dt><dd>{{ environmentTime(diagnostics?.checked_at) }}</dd
        ><dt>執行裝置來源</dt
        ><dd
          ><code>{{ executionDevice?.source || '未知' }}</code></dd
        ><dt>裝置查詢時間</dt><dd>{{ environmentTime(executionDevice?.checked_at) }}</dd></dl
      >
      <p class="footnote"
        >範圍為目前選定的引擎。提交時會重新查詢原引擎，不以此顯示快照阻擋任務。未取得裝置回報時，不因空裝置清單、離線或本機
        CUDA 診斷推定無 GPU。</p
      >
      <ul v-if="diagnostics?.warnings.length" class="environment-warnings"
        ><li v-for="(warning, index) in diagnostics.warnings" :key="index">{{ warning }}</li></ul
      >
    </details>
    <button type="button" class="secondary engine-settings" @click="emit('settings')"
      >設定連線</button
    >
  </article>
</template>
