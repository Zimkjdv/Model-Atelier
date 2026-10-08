<script setup lang="ts">
import type { JobMeasurements } from './jobMeasurements'
defineProps<{ item?: JobMeasurements | null }>()
const seconds = (v: number | null | undefined) => typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v.toFixed(3) + ' 秒' : '未知'
const gib = (v: number | null | undefined) => typeof v === 'number' && Number.isFinite(v) && v >= 0 ? (v / 1024 ** 3).toFixed(2) + ' GiB' : '未知'
</script>
<template>
  <details class="job-measurements"><summary>任務耗時與資源來源</summary>
    <template v-if="item?.schema_version === 1">
      <p>平台提交至終態觀察：{{ seconds(item.dispatch_to_observation_seconds) }}</p><p>原引擎執行起訖：{{ seconds(item.engine_execution_seconds) }}</p>
      <p>{{ item.timing_note }}</p><p>原引擎：{{ item.engine_url }}</p>
      <template v-if="item.resources_before_submission"><p>提交前快照：{{ item.resources_before_submission.captured_at }} · {{ item.resources_before_submission.source }}</p>
        <p>引擎 RAM 已用／可用：{{ gib(item.resources_before_submission.ram.used) }}／{{ gib(item.resources_before_submission.ram.free) }}</p>
        <p v-for="(device,i) in item.resources_before_submission.devices" :key="i">{{ device.name || '未知裝置' }} · {{ device.type || '類型未知' }} · {{ ['cuda','mps','hip'].includes(device.type || '') ? '裝置顯存' : '裝置記憶體' }}已用／可用：{{ gib(device.vram.used) }}／{{ gib(device.vram.free) }}</p>
        <p>{{ item.resources_before_submission.note }}</p></template>
      <p>任務專用 VRAM 峰值：未知；本階段沒有連續或程序專用量測。</p>
    </template><p v-else>此紀錄沒有提交時的耗時與資源量測，保持未知，不從目前主機或匯入時間回填。</p>
  </details>
</template>
<style scoped>.job-measurements{margin:14px 0;font-size:12px;line-height:1.8;overflow-wrap:anywhere}summary{cursor:pointer;color:var(--text-notice)}</style>
