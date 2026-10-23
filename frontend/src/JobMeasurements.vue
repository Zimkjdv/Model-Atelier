<script setup lang="ts">
import type { JobMeasurements } from './jobMeasurements'
defineProps<{ item?: JobMeasurements | null }>()
const seconds = (v: number | null | undefined) =>
  typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v.toFixed(3) + ' 秒' : '未知'
const gib = (v: number | null | undefined) =>
  typeof v === 'number' && Number.isFinite(v) && v >= 0
    ? (v / 1024 ** 3).toFixed(2) + ' GiB'
    : '未知'
const reason = (value: string | null) =>
  ({
    job_terminal: '已確認任務終態，取樣已凍結',
    sampling_limit: '已達一小時／1800 次上限',
    platform_shutdown: '平台停止，保留部分觀察',
    capacity_limit: '同時取樣已達 16 項上限',
  })[value || ''] || '背景取樣中；重新整理任務狀態可取得目前觀察'
</script>
<template>
  <details class="job-measurements"
    ><summary>任務耗時與資源來源</summary>
    <template v-if="item?.schema_version === 1">
      <p>平台提交至終態觀察：{{ seconds(item.dispatch_to_observation_seconds) }}</p
      ><p>原引擎執行起訖：{{ seconds(item.engine_execution_seconds) }}</p>
      <p>{{ item.timing_note }}</p
      ><p>原引擎：{{ item.engine_url }}</p>
      <template v-if="item.resources_before_submission"
        ><p
          >提交前快照：{{ item.resources_before_submission.captured_at }} ·
          {{ item.resources_before_submission.source }}</p
        >
        <p
          >引擎 RAM 已用／可用：{{ gib(item.resources_before_submission.ram.used) }}／{{
            gib(item.resources_before_submission.ram.free)
          }}</p
        >
        <p v-for="(device, i) in item.resources_before_submission.devices" :key="i"
          >{{ device.name || '未知裝置' }} · {{ device.type || '類型未知' }} ·
          {{
            ['cuda', 'mps', 'hip'].includes(device.type || '') ? '裝置顯存' : '裝置記憶體'
          }}已用／可用：{{ gib(device.vram.used) }}／{{ gib(device.vram.free) }}</p
        >
        <p>{{ item.resources_before_submission.note }}</p></template
      >
      <div
        v-if="item.continuous_resources?.schema_version === 1"
        role="group"
        aria-label="連續資源取樣"
      >
        <h3>原引擎連續資源取樣</h3>
        <p>{{ reason(item.continuous_resources.end_reason) }}</p>
        <p>來源：{{ item.continuous_resources.source }}</p>
        <p
          >開始：{{ item.continuous_resources.started_at }} · 結束：{{
            item.continuous_resources.ended_at || '尚未結束'
          }}</p
        >
        <p
          >每輪至少 {{ item.continuous_resources.interval_seconds }} 秒；成功
          {{ item.continuous_resources.successes }}／嘗試
          {{ item.continuous_resources.attempts }} 次；失敗
          {{ item.continuous_resources.failures }} 次；超過兩倍間隔
          {{ item.continuous_resources.gaps }} 次。</p
        >
        <p>引擎主機 RAM 觀察最高已用量：{{ gib(item.continuous_resources.ram_max_used_bytes) }}</p>
        <p v-for="(device, i) in item.continuous_resources.devices" :key="i"
          >{{ device.name || '未知裝置' }} · {{ device.type || '類型未知' }} · 裝置
          {{ device.index ?? '未知' }} 觀察最高已用量：{{ gib(device.max_used_bytes) }}</p
        >
        <p>{{ item.continuous_resources.note }}</p>
        <details v-if="item.continuous_resources.samples.length"
          ><summary>最近取樣（最多 {{ item.continuous_resources.retained_points }} 筆）</summary>
          <ol
            ><li v-for="(sample, i) in item.continuous_resources.samples" :key="i"
              >{{ sample.at }} · RAM {{ gib(sample.ram_used_bytes)
              }}<template v-for="reading in sample.devices" :key="reading.device">
                · 裝置 {{ reading.device + 1 }}：{{ gib(reading.used_bytes) }}</template
              >{{ sample.error ? ' · 來源不可用，保持未知' : '' }}</li
            ></ol
          >
        </details>
      </div>
      <p v-else>連續資源取樣：無紀錄，不回填歷史資料。</p>
      <p>任務專用 VRAM 峰值：未知；原引擎未提供可靠的單一任務程序歸屬。</p> </template
    ><p v-else>此紀錄沒有提交時的耗時與資源量測，保持未知，不從目前主機或匯入時間回填。</p>
  </details>
</template>
<style scoped>
.job-measurements {
  margin: 14px 0;
  font-size: 12px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
summary {
  cursor: pointer;
  color: var(--text-notice);
}
</style>
