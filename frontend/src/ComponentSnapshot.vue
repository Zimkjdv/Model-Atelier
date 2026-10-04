<script setup lang="ts">
import { fluxRoles, type ComponentSnapshot } from './fluxSettings'
import { safeMetadataUrl } from './modelMetadata'
defineProps<{ items?: ComponentSnapshot[] | null }>()
</script>
<template>
  <details v-if="items?.length" class="component-snapshot"><summary>提交時四元件版本與來源</summary>
    <article v-for="item in items" :key="item.role"><strong>{{ fluxRoles.find(role => role.key === item.role)?.label || item.role }}</strong>
      <p>{{ item.name }} · 版本 {{ item.version || '未知' }}</p>
      <p v-if="safeMetadataUrl(item.source_url)"><a :href="safeMetadataUrl(item.source_url)!" target="_blank" rel="noopener">登記來源</a></p>
      <p>SHA256：{{ item.sha256 || '未知' }}</p><p>授權：{{ item.license_name || '未知' }}</p>
    </article><p class="footnote">原任務快照；未驗證目前權重，不從新登記資料回填。</p>
  </details>
</template>
<style scoped>
.component-snapshot{margin:18px 0;font-size:12px;overflow-wrap:anywhere}.component-snapshot summary{cursor:pointer}.component-snapshot article{border-top:1px solid var(--border-control);padding:14px 0}.component-snapshot p{line-height:1.6}.component-snapshot a{color:var(--focus-ring)}
</style>
