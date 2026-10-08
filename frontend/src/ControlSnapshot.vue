<script setup lang="ts">
import type { ControlMetadata } from './controlSettings'
import { architectureLabel, fileSize, safeMetadataUrl } from './modelMetadata'
defineProps<{items?:ControlMetadata[]|null}>()
</script>
<template><details v-if="items?.length" class="control-snapshot"><summary>提交時 ControlNet 版本與來源</summary><article v-for="item in items" :key="item.name"><strong>{{item.name}}</strong><p>版本 {{item.version || '未知'}} · {{architectureLabel(item.architecture)}} · 類型 {{item.kind || '未知'}}</p><p>SHA256 {{item.sha256 || '未知'}}</p><p>大小 {{fileSize(item.size_bytes)}} · 授權 {{item.license_name || '未知'}}</p><a v-if="safeMetadataUrl(item.source_url)" :href="safeMetadataUrl(item.source_url)" target="_blank" rel="noopener noreferrer">原登記來源 ↗</a></article><p class="footnote">原任務不可變快照；不使用新登記值回填，也不代表目前檔案已驗證。</p></details></template>
<style scoped>.control-snapshot{margin:14px 0;padding:12px;border:1px solid var(--border-control);border-radius:8px;font-size:12px;overflow-wrap:anywhere}summary{cursor:pointer}p{line-height:1.7}a{color:var(--text-notice)}</style>
