<script setup lang="ts">
import { environmentSize, environmentText } from './environmentTypes'
import type { EnvironmentDevice } from './environmentTypes'
defineProps<{ devices: EnvironmentDevice[]; memoryLabel: string }>()
</script>

<template>
  <div class="environment-devices">
    <article v-for="(device, ordinal) in devices" :key="`${device.index ?? 'unknown'}:${ordinal}`" class="environment-device">
      <div class="environment-device-heading"><strong>{{ environmentText(device.name) }}</strong><span>{{ environmentText(device.type) }} · 裝置索引 {{ device.index ?? '未知' }}</span></div>
      <p>{{ device.type === 'cpu' ? '引擎回報 CPU 裝置記憶體' : memoryLabel }}：可用 {{ environmentSize(device.vram?.free) }} / 總量 {{ environmentSize(device.vram?.total) }}</p>
      <details><summary>記憶體細節</summary><dl>
        <dt>回報裝置記憶體已用</dt><dd>{{ environmentSize(device.vram?.used) }}</dd>
        <dt>Torch 記憶體總量</dt><dd>{{ environmentSize(device.torch_vram?.total) }}</dd>
        <dt>Torch 記憶體可用</dt><dd>{{ environmentSize(device.torch_vram?.free) }}</dd>
        <dt>Torch 記憶體已用</dt><dd>{{ environmentSize(device.torch_vram?.used) }}</dd>
      </dl></details>
    </article>
  </div>
</template>

<style scoped>
.environment-devices{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:18px 0}.environment-device{border:1px solid #35433b;border-radius:8px;padding:15px;min-width:0;overflow-wrap:anywhere;background:#17201a}.environment-device-heading{display:flex;gap:8px;flex-direction:column;font-size:12px}.environment-device-heading span{font-size:10px;color:#9eafa2}.environment-device p{font-size:11px}.environment-device details{font-size:11px}.environment-device summary{cursor:pointer;color:#bfd3b6}.environment-device dl{display:grid;grid-template-columns:1fr 1fr;gap:9px}.environment-device dt{color:#9eafa2}.environment-device dd{margin:0}@media(max-width:850px){.environment-devices{grid-template-columns:1fr}}
</style>
