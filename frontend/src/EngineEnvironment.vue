<script setup lang="ts">
import { computed } from 'vue'
import EnvironmentDevices from './EnvironmentDevices.vue'
import { cudaStatus, environmentSize, environmentText, environmentTime } from './environmentTypes'
import type { EngineReport } from './environmentTypes'
const props = defineProps<{ engine: EngineReport | null; selectedUrl: string }>()
const emit = defineEmits<{ settings: [] }>()
const current = computed(() => props.engine && (!props.selectedUrl || props.engine.url === props.selectedUrl) ? props.engine : null)
const diagnostics = computed(() => current.value?.diagnostics ?? null)
const available = computed(() => current.value?.connected && diagnostics.value?.status === 'available' && diagnostics.value.matches_selected_engine !== false)
const system = computed(() => available.value ? diagnostics.value?.system : null)
const statusLabel = computed(() => available.value ? '引擎回報可用' : diagnostics.value?.status === 'invalid' ? '回報資料無效' : current.value?.connected ? '尚無診斷回報' : '未連線')
</script>

<template>
  <article class="panel engine-environment">
    <div class="panel-heading"><div><h2>選定引擎的執行環境</h2><p class="muted">來源：ComfyUI /system_stats · 範圍：目前選定的引擎。</p></div><span class="status" :class="{ connected: available }">{{ statusLabel }}</span></div>
    <div class="environment-endpoint">{{ current?.url || selectedUrl || '尚未取得引擎位址' }}<span>查詢時間：{{ environmentTime(diagnostics?.checked_at) }}</span></div>
    <p v-if="!available" class="environment-warning" role="status">{{ current?.error || (diagnostics?.status === 'invalid' ? '引擎回報資料不完整，環境欄位目前未知。' : current?.connected ? '已連接服務，尚未取得可用的環境診斷資料。' : '請確認服務已啟動且位址正確。') }} <button type="button" class="secondary" @click="emit('settings')">設定連線 →</button></p>
    <dl class="environment-versions">
      <div><dt>ComfyUI</dt><dd>{{ environmentText(system?.comfyui) }}</dd></div>
      <div><dt>引擎 Python</dt><dd>{{ environmentText(system?.python) }}</dd></div>
      <div><dt>引擎 PyTorch</dt><dd>{{ environmentText(system?.pytorch) }}</dd></div>
      <div><dt>CUDA 版本（引擎回報）</dt><dd>{{ environmentText(system?.cuda_runtime) }}</dd></div>
      <div><dt>CUDA 可用（引擎回報）</dt><dd>{{ cudaStatus(system?.cuda_available) }}</dd></div>
      <div><dt>驅動（引擎回報）</dt><dd>{{ environmentText(system?.driver) }}</dd></div>
    </dl>
    <EnvironmentDevices v-if="available && diagnostics?.devices.length" :devices="diagnostics.devices" memory-label="引擎回報 VRAM"/>
    <p v-else-if="available" class="footnote">引擎尚未回報可辨識的裝置資料。</p>
    <p v-if="available" class="footnote">引擎回報 RAM：已用 {{ environmentSize(diagnostics?.ram.used) }} · 可用 {{ environmentSize(diagnostics?.ram.free) }} · 總量 {{ environmentSize(diagnostics?.ram.total) }} · OS：{{ environmentText(system?.os) }}。</p>
    <ul v-if="diagnostics?.warnings.length" class="environment-warnings"><li v-for="(warning, index) in diagnostics.warnings" :key="index">{{ warning }}</li></ul>
    <p class="footnote">未知欄位表示此引擎未提供有效資料。裝置是引擎回報，不能證明每項任務實際使用哪張 GPU；回報的可用 VRAM 可能包含可回收快取，與平台 nvidia-smi 數值可能不同。</p>
  </article>
</template>

<style scoped>
.engine-environment .panel-heading{align-items:start;gap:18px}.environment-endpoint{border-top:1px solid #35403a;padding-top:15px;margin-top:18px;color:#acc1a5;font:11px monospace;overflow-wrap:anywhere}.environment-endpoint span{display:block;color:#929f98;font:10px Inter,"Microsoft JhengHei",sans-serif;margin-top:8px}.environment-warning{font-size:12px;color:#ebc4a1}.environment-warning button{margin:8px}.environment-versions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:22px 0}.environment-versions>div{min-width:0}.environment-versions dt{font-size:10px;color:#8e9e96}.environment-versions dd{margin:8px 0 0;font-size:12px;overflow-wrap:anywhere}.environment-warnings{padding-left:20px;font-size:11px;line-height:1.8;color:#b7aa94}@media(max-width:850px){.environment-versions{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:500px){.environment-versions{grid-template-columns:1fr}.engine-environment .panel-heading{flex-direction:column}}
</style>
