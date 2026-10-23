<script setup lang="ts">
import { referenceRoles, type ReferenceComponent } from './adapterSettings'
import { safeMetadataUrl } from './modelMetadata'
defineProps<{ items?: ReferenceComponent[] | null }>()
</script>
<template>
  <details v-if="items?.length" class="reference-components">
    <summary>提交時的 adapter 與影像編碼器</summary>
    <article v-for="item in items" :key="item.role">
      <strong>{{ referenceRoles.find((r) => r.role === item.role)?.label || item.role }}</strong>
      <p
        >{{ item.name }} · {{ item.family || '未知家族' }} ·
        {{ item.architecture || '未知架構' }}</p
      >
      <p>版本：{{ item.version || '未知' }}</p>
      <p>SHA256：{{ item.sha256 || '未知' }}</p>
      <p>大小：{{ item.size_bytes ?? '未知' }} bytes · 授權：{{ item.license_name || '未知' }}</p>
      <a
        v-if="safeMetadataUrl(item.source_url)"
        :href="safeMetadataUrl(item.source_url)"
        target="_blank"
        rel="noopener"
        >登記來源 ↗</a
      >
    </article>
    <p>原任務快照；登記資訊不是檔案驗證或品質保證。節點個別版本未由引擎回報時保持未知。</p>
  </details>
</template>
<style scoped>
.reference-components {
  margin: 18px 0;
  font-size: 12px;
  overflow-wrap: anywhere;
  line-height: 1.8;
}
summary {
  cursor: pointer;
}
article {
  border-top: 1px solid var(--border-control);
  padding: 12px 0;
}
a {
  color: var(--focus-ring);
}
</style>
